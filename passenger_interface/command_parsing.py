import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


UNKNOWN_COMMAND = "unknown"


class CommandAction(str, Enum):
    """Actions the language model is allowed to return."""

    EXECUTE_EMERGENCY_STOP = "EXECUTE_EMERGENCY_STOP"
    EXECUTE_LANE_FOLLOWING = "EXECUTE_LANE_FOLLOWING"
    EXECUTE_LANE_CHANGE_LEFT = "EXECUTE_LANE_CHANGE_LEFT"
    EXECUTE_LANE_CHANGE_RIGHT = "EXECUTE_LANE_CHANGE_RIGHT"
    INCREASE_VELOCITY = "INCREASE_VELOCITY"
    DECREASE_VELOCITY = "DECREASE_VELOCITY"
    STOP_AND_LET_SB_BOARD = "STOP_AND_LET_SB_BOARD"
    STOP_AND_LET_SB_EXIT = "STOP_AND_LET_SB_EXIT"
    STOP_AND_PARK = "STOP_AND_PARK"
    STAY_BEHIND_THE_VEHICLE_AHEAD = (
        "STAY_BEHIND_THE_VEHICLE_AHEAD"
    )
    TURN_RIGHT = "TURN_RIGHT"
    PERFORM_U_TURN = "PERFORM_U_TURN"
    LEAVE_ROUNDABOUT_AT_EXIT_X = "LEAVE_ROUNDABOUT_AT_EXIT_X"
    CROSS_JUNCTION_STRAIGHT = "CROSS_JUNCTION_STRAIGHT"
    TURN_LEFT = "TURN_LEFT"
    DRIVE_BACK_TO_START_POINT = "DRIVE_BACK_TO_START_POINT"
    DRIVE_MORE_COMFORTABLY = "DRIVE_MORE_COMFORTABLY"
    DRIVE_MORE_SPORTILY = "DRIVE_MORE_SPORTILY"
    RESUME_RIDE = "RESUME_RIDE"
    KEEP_MORE_DISTANCE = "KEEP_MORE_DISTANCE"
    SET_NEW_GOAL_POINT = "SET_NEW_GOAL_POINT"
    UNKNOWN = "UNKNOWN"


class CommandInterpretation(BaseModel):
    """Validated result of transcript correction and classification."""

    model_config = ConfigDict(extra="forbid")

    corrected_text: str = Field(
        description="Minimally corrected version of the transcript"
    )
    action: CommandAction


CANONICAL_COMMANDS = {
    action.value.lower()
    for action in CommandAction
    if action is not CommandAction.UNKNOWN
}

COMMAND_ALIASES = {
    "perform_emergency_stop": "execute_emergency_stop",
    "follow_lane": "execute_lane_following",
    "change_lane_left": "execute_lane_change_left",
    "change_lane_right": "execute_lane_change_right",
    "drive_faster": "increase_velocity",
    "slow_down": "decrease_velocity",
    "decrease_velocity": "decrease_velocity",
    "stop_and_let_someone_board": "stop_and_let_sb_board",
    "stop_and_let_me_exit": "stop_and_let_sb_exit",
    "stay_behind_the_vehicle_ahead": "stay_behind_the_vehicle_ahead",
    "perform_u_turn": "perform_u_turn",
    "cross_junction_straight": "cross_junction_straight",
    "accelerate_more_gently": "drive_more_comfortably",
    "drive_more_comfortably": "drive_more_comfortably",
    "drive_sportier": "drive_more_sportily",
    "leave_roundabout_at_x_th_exit": "leave_roundabout_at_exit_x",
    "drive_to_xyz": "set_new_goal_point",
}

def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def normalize_correction_output(output: str) -> str:
    """Extract corrected transcript text from an LLM response."""
    text = output.strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = text.split("```", 1)[0].strip()
    text = re.sub(
        r"^(?:correction|corrected transcript)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = text.splitlines()[0].strip() if text else ""
    return text.strip().strip("\"'")


def normalize_destination_text(destination: str) -> str:
    """Normalize a spoken named destination for location-table lookup."""
    text = destination.lower().strip()
    text = re.sub(r"[\s.,!?;:]+$", "", text)
    text = re.sub(r"^the\s+", "", text)
    return text


def extract_destination_text(command: str) -> str:
    """Extract a named destination from a corrected English command."""
    match = re.search(
        r"(?:drive to|go to)\s+(.+)$",
        command,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""

    return normalize_destination_text(match.group(1))


def normalize_llm_command(output: str) -> str:
    """Convert an LLM response into a strict canonical command key."""
    text = output.strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = text.split("```", 1)[0].strip()
    text = text.splitlines()[0].strip() if text else ""
    text = re.sub(
        r"^(?:classification_model|classification_agent|action)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^\s*\d+\s*[.)-]\s*", "", text)
    text = text.split(":", 1)[0].strip()

    key = _normalize_key(text)
    if key in CANONICAL_COMMANDS:
        return key

    alias = COMMAND_ALIASES.get(key)
    if alias is not None:
        return alias

    if key.startswith("execute_"):
        unprefixed_key = key.removeprefix("execute_")
        if unprefixed_key in CANONICAL_COMMANDS:
            return unprefixed_key

    return UNKNOWN_COMMAND


def simulation_classify(text: str) -> str:
    """Classify clear English commands while running in simulation mode."""
    command = " ".join(re.findall(r"[a-z0-9]+", text.lower()))

    if "emergency" in command or "stop immediately" in command:
        return "execute_emergency_stop"

    if (
        "change lane left" in command
        or "move to the left lane" in command
        or "go to the left lane" in command
    ):
        return "execute_lane_change_left"

    if (
        "change lane right" in command
        or "move to the right lane" in command
        or "go to the right lane" in command
    ):
        return "execute_lane_change_right"

    if "u turn" in command or "turn around" in command:
        return "perform_u_turn"

    if "roundabout" in command:
        return "leave_roundabout_at_exit_x"

    if (
        "drive back to start" in command
        or "go back to start" in command
        or "return to start" in command
    ):
        return "drive_back_to_start_point"

    if command.startswith("drive to ") or command.startswith("go to "):
        return "set_new_goal_point"

    if (
        "drive more comfortably" in command
        or "accelerate more gently" in command
        or "more comfortable" in command
    ):
        return "drive_more_comfortably"

    if "drive sportier" in command or "more sporty" in command:
        return "drive_more_sportily"

    if (
        "drive faster" in command
        or "go faster" in command
        or "speed up" in command
        or "increase speed" in command
        or "increase velocity" in command
        or command in {"faster", "faster please"}
    ):
        return "increase_velocity"

    if (
        "drive slower" in command
        or "go slower" in command
        or "slow down" in command
        or "decrease speed" in command
        or "decrease velocity" in command
        or command in {"slower", "slower please"}
    ):
        return "decrease_velocity"

    if "let someone board" in command or "pick up" in command:
        return "stop_and_let_sb_board"

    if (
        "let me exit" in command
        or "let me out" in command
        or "get out of the car" in command
    ):
        return "stop_and_let_sb_exit"

    if "park" in command:
        return "stop_and_park"

    if (
        "stay behind" in command
        or "do not overtake" in command
        or "don t overtake" in command
    ):
        return "stay_behind_the_vehicle_ahead"

    if "turn right" in command:
        return "turn_right"

    if "turn left" in command:
        return "turn_left"

    if "keep more distance" in command or "increase distance" in command:
        return "keep_more_distance"

    if "resume" in command or "continue the ride" in command:
        return "resume_ride"

    if (
        "junction" in command
        and ("straight" in command or "cross" in command)
    ):
        return "cross_junction_straight"

    if (
        "follow the lane" in command
        or "continue in this lane" in command
        or "drive straight" in command
    ):
        return "execute_lane_following"

    return UNKNOWN_COMMAND
