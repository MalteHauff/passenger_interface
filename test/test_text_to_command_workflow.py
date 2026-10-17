import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from passenger_interface.text_to_command_workflow import TextToCommandWorkflow


class FakeOllamaClient:
    def __init__(self, response_content):
        self.response_content = response_content
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(content=self.response_content)
        )


def test_workflow_uses_one_constrained_non_thinking_call():
    client = FakeOllamaClient(
        json.dumps({
            "corrected_text": "Take the third exit at the roundabout.",
            "action": "LEAVE_ROUNDABOUT_AT_EXIT_X",
        })
    )
    workflow = TextToCommandWorkflow(
        "qwen3.5:4b",
        client=client,
    )

    action = workflow.text_to_command(
        "Take the third exist at the roundabout."
    )

    assert action == "LEAVE_ROUNDABOUT_AT_EXIT_X"
    assert workflow.last_corrected_text == (
        "Take the third exit at the roundabout."
    )
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "qwen3.5:4b"
    assert call["think"] is False
    assert call["stream"] is False
    assert call["keep_alive"] == "30m"
    assert call["options"] == {
        "temperature": 0,
        "num_ctx": 2048,
        "num_predict": 96,
    }
    assert "CommandAction" in call["format"]["$defs"]


def test_workflow_preserves_original_text_when_correction_is_disabled():
    client = FakeOllamaClient(
        json.dumps({
            "corrected_text": "Go faster.",
            "action": "INCREASE_VELOCITY",
        })
    )
    workflow = TextToCommandWorkflow(
        "qwen3.5:4b",
        enable_stt_correction=False,
        client=client,
    )

    workflow.text_to_command("Go fast.")

    assert workflow.last_corrected_text == "Go fast."


def test_workflow_rejects_invalid_structured_output():
    client = FakeOllamaClient(
        '{"corrected_text":"Fly.","action":"FLY"}'
    )
    workflow = TextToCommandWorkflow("qwen3.5:4b", client=client)

    with pytest.raises(ValidationError):
        workflow.text_to_command("Fly.")
