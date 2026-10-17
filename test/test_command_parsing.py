import pytest
from pydantic import ValidationError

from passenger_interface.command_parsing import (
    CANONICAL_COMMANDS,
    CommandAction,
    CommandInterpretation,
    extract_destination_text,
    normalize_correction_output,
    normalize_destination_text,
    normalize_llm_command,
    simulation_classify,
    UNKNOWN_COMMAND,
)


def test_structured_command_schema_matches_canonical_commands():
    structured_commands = {
        action.value.lower()
        for action in CommandAction
        if action is not CommandAction.UNKNOWN
    }
    assert structured_commands == CANONICAL_COMMANDS


def test_structured_command_result_validates_allowed_action():
    result = CommandInterpretation.model_validate_json(
        '{"corrected_text":"Turn left.","action":"TURN_LEFT"}'
    )
    assert result.corrected_text == "Turn left."
    assert result.action is CommandAction.TURN_LEFT


def test_structured_command_result_rejects_unknown_fields_and_actions():
    with pytest.raises(ValidationError):
        CommandInterpretation.model_validate_json(
            '{"corrected_text":"Fly.","action":"FLY"}'
        )

    with pytest.raises(ValidationError):
        CommandInterpretation.model_validate_json(
            '{"corrected_text":"Stop.",'
            '"action":"EXECUTE_EMERGENCY_STOP","reason":"urgent"}'
        )


def test_simulation_speed_commands_from_runtime_log():
    assert simulation_classify(
        "Let's drive faster."
    ) == "increase_velocity"
    assert simulation_classify(
        "Drive faster."
    ) == "increase_velocity"
    assert simulation_classify(
        "Go faster."
    ) == "increase_velocity"


def test_simulation_classifier_prefers_specific_commands():
    assert simulation_classify(
        "Accelerate more gently."
    ) == "drive_more_comfortably"
    assert simulation_classify(
        "Take the third exit at the roundabout."
    ) == "leave_roundabout_at_exit_x"


def test_simulation_classifier_rejects_non_command_text():
    assert simulation_classify("Thank you very much.") == UNKNOWN_COMMAND
    assert simulation_classify(". . . .") == UNKNOWN_COMMAND


def test_normalize_uppercase_enum_from_runtime_log():
    assert normalize_llm_command("TURN_LEFT") == "turn_left"
    assert normalize_llm_command(
        "EXECUTE_INCREASE_VELOCITY"
    ) == "increase_velocity"


def test_normalize_human_readable_alias_from_runtime_log():
    assert normalize_llm_command(
        "Drive more comfortably"
    ) == "drive_more_comfortably"


def test_normalize_numbered_and_prefixed_outputs():
    assert normalize_llm_command(
        "5. INCREASE_VELOCITY"
    ) == "increase_velocity"
    assert normalize_llm_command(
        "classification_model: 6. DECREASE_VELOCITY"
    ) == "decrease_velocity"
    assert normalize_llm_command(
        "4. change_lane_right: Go to the right lane."
    ) == "execute_lane_change_right"


def test_normalize_rejects_unconstrained_llm_text():
    assert normalize_llm_command(
        "I'm ready to assist you."
    ) == UNKNOWN_COMMAND


def test_normalize_correction_output():
    assert normalize_correction_output(
        "Correction: Resume the ride."
    ) == "Resume the ride."
    assert normalize_correction_output(
        '```text\n"Resume the ride."\n```'
    ) == "Resume the ride."


def test_normalize_named_destination_for_location_lookup():
    assert normalize_destination_text("the airport.") == "airport"
    assert normalize_destination_text(" Supermarket! ") == "supermarket"
    assert normalize_destination_text("university") == "university"


def test_extract_destination_from_corrected_command():
    assert extract_destination_text(
        "Go to the airport."
    ) == "airport"
    assert extract_destination_text(
        "Drive to the supermarket!"
    ) == "supermarket"
