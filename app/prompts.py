"""Prompt construction for the Phase 1 contributor simulation."""

import json


OUTPUT_SCHEMA = {
    "issue_summary": "string",
    "relevant_files": [
        {
            "path": "string",
            "reason": "string",
        }
    ],
    "implementation_plan": ["string"],
    "tests": ["string"],
    "risks": ["string"],
}


def build_prompt(repository_context: str, issue: str) -> str:
    """Build a bounded prompt from supplied evidence.

    The model is explicitly told not to invent repository details that are not
    present in the context. This is the central Phase 1 design constraint:
    tools provide evidence and Gemma provides reasoning.
    """

    schema = json.dumps(OUTPUT_SCHEMA, indent=2)
    return f"""You are ContribSim, a contributor simulator for an unfamiliar open-source repository.

Use only the repository context and issue below. Do not claim that files,
functions, or behavior exist unless they are supported by the context.
Reason about the specific issue rather than giving generic repository advice.

Return only valid JSON. Do not wrap it in Markdown code fences. The JSON must
match this shape exactly:
{schema}

Repository context:
---
{repository_context}
---

Issue:
---
{issue}
---

Produce a concise but useful contribution plan.
"""
