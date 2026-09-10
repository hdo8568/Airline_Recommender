from __future__ import annotations

import json
from datetime import date

from .conversation import SCHEMA
from .prompts import intent_system_prompt
from .providers import ServiceError, request_json


CONTEXT_FIELDS = (
    "clinic",
    "destination",
    "procedure_date",
    "arrival_deadline",
    "return_not_before",
    "return_not_before_at",
    "outbound_date",
    "return_date",
    "policy_note",
)


def context_for_model(context):
    return {key: context[key] for key in CONTEXT_FIELDS if key in context}


class SafeClaudeIntent:
    def __init__(self, key, model, http=request_json):
        if not key or not model:
            raise ValueError("Configure ANTHROPIC_API_KEY and ANTHROPIC_MODEL before enabling Claude.")
        self.key = key
        self.model = model
        self.http = http

    def __call__(self, text, state):
        payload = {
            "today": date.today().isoformat(),
            "clinic_context": context_for_model(state.get("context", {})),
            "preferences": state["preferences"],
            "recent_history": state.get("history", [])[-6:],
            "message": text,
        }
        response = self.http(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "max_tokens": 600,
                "system": intent_system_prompt(),
                "messages": [{"role": "user", "content": json.dumps(payload)}],
                "tools": [{
                    "name": "interpret_trip",
                    "description": "Extract supported flight preferences or classify the question.",
                    "input_schema": SCHEMA,
                }],
                "tool_choice": {"type": "tool", "name": "interpret_trip"},
            },
        )
        if not isinstance(response, dict) or not isinstance(response.get("content"), list):
            raise ServiceError("The AI returned an unexpected response.")
        blocks = [
            block for block in response["content"]
            if isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("name") == "interpret_trip"
        ]
        if len(blocks) != 1 or not isinstance(blocks[0].get("input"), dict):
            raise ServiceError("The AI returned an invalid preference update. Please try a simpler message.")
        return blocks[0]["input"]
