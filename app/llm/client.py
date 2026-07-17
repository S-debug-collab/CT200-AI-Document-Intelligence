from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

MAX_RETRIES = 2


class TestCaseIdea(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    steps: str = Field(..., min_length=3)
    expected_result: str = Field(..., min_length=3)
    risk_level: str = Field(..., pattern="^(low|medium|high)$")


class TestCaseList(BaseModel):
    test_cases: list[TestCaseIdea] = Field(..., min_length=3, max_length=5)


SYSTEM_PROMPT = """
You are a senior QA engineer.

You will receive ONLY one section from a device manual.

Your task is to generate 3-5 executable test cases STRICTLY from the provided text.

Rules:
- Use ONLY information explicitly present in the manual section.
- Do NOT invent alarm names, thresholds, error codes, measurements, timings, or device behaviors.
- If the section contains numbers, limits, warning messages, or error codes, use them.
- If the section is general, create validation test cases that verify the documented behavior.
- Never use outside medical knowledge.
- If something is not written in the manual, do not mention it.

Return ONLY JSON.

{
  "test_cases":[
    {
      "title":"",
      "steps":"",
      "expected_result":"",
      "risk_level":"low|medium|high"
    }
  ]
}
"""


@dataclass
class GenerationOutcome:
    status: str
    test_cases: Optional[list[dict]]
    raw_responses: list[str]
    error: Optional[str]
    attempts: int


def _extract_json(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start:brace_end + 1]
    return text


class LLMClient:
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def complete(self, system: str, user: str) -> str:
        text = user.lower()
        cases = []

        numbers = re.findall(
            r"\d+(?:\.\d+)?\s*(?:mmhg|%|seconds?|minutes?|bpm|cm)",
            user,
            re.IGNORECASE,
        )
        error_codes = sorted(set(re.findall(r"\bE\d\b", user)))

        if error_codes:
            for code in error_codes[:2]:
                cases.append(
                    {
                        "title": f"Device correctly handles {code} condition",
                        "steps": f"Induce the condition described for {code} in the manual text and observe device response.",
                        "expected_result": f"Device displays {code} and follows the documented behavior for it.",
                        "risk_level": "high",
                    }
                )

        if numbers:
            cases.append(
                {
                    "title": "Boundary value at documented threshold",
                    "steps": f"Set the relevant parameter to just below, at, and just above the threshold ({numbers[0]}) mentioned in this section.",
                    "expected_result": "Device behavior transitions exactly at the documented threshold, matching the manual.",
                    "risk_level": "medium",
                }
            )

        cases.append(
            {
                "title": "Nominal path matches documented behavior",
                "steps": "Exercise the feature described in this section under normal, in-range conditions.",
                "expected_result": "Device behaves exactly as described in the section text, with no error condition raised.",
                "risk_level": "low",
            }
        )

        cases.append(
            {
                "title": "Section text is reflected in user-facing documentation/UI",
                "steps": "Cross-check the on-device UI strings / user manual wording against this section's current text.",
                "expected_result": "No contradiction between this section and the on-device behavior or other manual sections that reference it.",
                "risk_level": "low",
            }
        )

        while len(cases) < 3:
            cases.append(
                {
                    "title": "Regression check for this section",
                    "steps": "Re-run prior passing test cases for this section after any firmware change.",
                    "expected_result": "All prior test cases for this section still pass.",
                    "risk_level": "low",
                }
            )

        return json.dumps({"test_cases": cases[:5]})


class RealLLMClient(LLMClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.base_url = base_url or os.environ.get(
            "LLM_BASE_URL",
            "https://api.groq.com/openai/v1",
        )
        self.model = model or os.environ.get(
            "LLM_MODEL",
            "llama-3.1-70b-versatile",
        )

        if not self.api_key:
            raise RuntimeError(
                "RealLLMClient requires LLM_API_KEY to be set (see .env.example)"
            )

    def complete(self, system: str, user: str) -> str:
        import requests

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
            },
            timeout=30,
        )

        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def generate_test_cases(
    client: LLMClient,
    section_text: str,
) -> GenerationOutcome:
    raw_responses = []
    last_error = None
    user_prompt = f"Manual section text:\n\n{section_text}"

    for attempt in range(1, MAX_RETRIES + 2):
        raw = client.complete(SYSTEM_PROMPT, user_prompt)
        raw_responses.append(raw)

        try:
            candidate = _extract_json(raw)
            parsed = TestCaseList.model_validate(json.loads(candidate))

            return GenerationOutcome(
                status="ok",
                test_cases=[tc.model_dump() for tc in parsed.test_cases],
                raw_responses=raw_responses,
                error=None,
                attempts=attempt,
            )

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            user_prompt = (
                f"Manual section text:\n\n{section_text}\n\n"
                f"Your previous response was invalid: {last_error}\n"
                f"Previous response was:\n{raw}\n\n"
                "Respond again with ONLY valid JSON matching the required shape."
            )

    return GenerationOutcome(
        status="failed",
        test_cases=None,
        raw_responses=raw_responses,
        error=last_error,
        attempts=MAX_RETRIES + 1,
    )
