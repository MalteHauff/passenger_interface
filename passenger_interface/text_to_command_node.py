import rclpy
from rclpy.node import Node
from adore_ros2_msgs.msg import PassengerRequest
import re
from std_msgs.msg import String

from .command_parsing import (
    CANONICAL_COMMANDS,
    extract_destination_text,
    normalize_llm_command,
    simulation_classify,
    UNKNOWN_COMMAND,
)


CMD_TO_TYPE = {
    "execute_emergency_stop": PassengerRequest.EXECUTE_EMERGENCY_STOP,
    "execute_lane_following": PassengerRequest.EXECUTE_LANE_FOLLOWING,
    "execute_lane_change_left": PassengerRequest.EXECUTE_LANE_CHANGE_LEFT,
    "execute_lane_change_right": PassengerRequest.EXECUTE_LANE_CHANGE_RIGHT,
    "increase_velocity": PassengerRequest.INCREASE_VELOCITY,
    "decrease_velocity": PassengerRequest.DECREASE_VELOCITY,
    "stop_and_let_sb_board": PassengerRequest.STOP_AND_LET_SB_BOARD,
    "stop_and_let_sb_exit": PassengerRequest.STOP_AND_LET_SB_EXIT,
    "stop_and_park": PassengerRequest.STOP_AND_PARK,
    "stay_behind_the_vehicle_ahead": PassengerRequest.STAY_BEHIND_THE_VEHICLE_AHEAD,
    "turn_right": PassengerRequest.TURN_RIGHT,
    "turn_left": PassengerRequest.TURN_LEFT,
    "perform_u_turn": PassengerRequest.PERFORM_U_TURN,
    "cross_junction_straight": PassengerRequest.CROSS_JUNCTION_STRAIGHT,
    "drive_back_to_start_point": PassengerRequest.DRIVE_BACK_TO_START_POINT,
    "drive_more_comfortably": PassengerRequest.DRIVE_MORE_COMFORTABLY,
    "drive_more_sportily": PassengerRequest.DRIVE_MORE_SPORTILY,
    "resume_ride": PassengerRequest.RESUME_RIDE,
    "keep_more_distance": PassengerRequest.KEEP_MORE_DISTANCE,
    "leave_roundabout_at_exit_x": PassengerRequest.LEAVE_ROUNDABOUT_AT_EXIT_X,
    "set_new_goal_point": PassengerRequest.SET_NEW_GOAL_POINT,
}

unmapped_commands = CANONICAL_COMMANDS.difference(CMD_TO_TYPE)
if unmapped_commands:
    raise RuntimeError(
        f"Canonical commands missing PassengerRequest mappings: "
        f"{sorted(unmapped_commands)}"
    )


def sanitize_factor(factor: float) -> float | None:
    if factor <= 0.0:
        return None

    return max(0.1, min(factor, 3.0))


def extract_change_factor(text: str) -> float | None:
    t = text.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|prozent)", t)
    if m:
        return 1.0 + float(m.group(1)) / 100.0

    m = re.search(r"(?:factor|multiplier)\s*(?:of\s*)?(\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))

    return None

def extract_percentage(text: str) -> float | None:
    t = text.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|prozent)", t)
    if m:
        return float(m.group(1)) / 100.0

    return None


def extract_factor(text: str) -> float | None:
    t = text.lower()

    m = re.search(r"(?:factor|multiplier)\s*(?:of\s*)?(\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))

    return None


def build_command_factor(text: str, command_type: int) -> float | None:
    percentage = extract_percentage(text)

    if percentage is not None:
        percentage = max(0.0, min(percentage, 0.9))

        if command_type in (
            PassengerRequest.DECREASE_VELOCITY,
            PassengerRequest.DRIVE_MORE_COMFORTABLY,
        ):
            return 1.0 - percentage

        return 1.0 + percentage

    factor = extract_factor(text)

    if factor is not None:
        return max(0.1, min(factor, 3.0))

    return None


def build_passenger_request(class_key: str, original_text: str, stamp_msg) -> PassengerRequest:
    req = PassengerRequest()
    req.header.stamp = stamp_msg
    req.numerical_detail = []
    req.text_detail = ""

    key = class_key.lower().strip()

    # roundabout exit number extraction
    if key == "leave_roundabout_at_exit_x":
        req.type = PassengerRequest.LEAVE_ROUNDABOUT_AT_EXIT_X
        m = re.search(r"(\d+)", original_text)
        exit_no = float(m.group(1)) if m else 1.0
        req.numerical_detail = [exit_no]
        return req

    # destination extraction: "drive to X" / "go to X"
    if key == "set_new_goal_point":
        req.type = PassengerRequest.SET_NEW_GOAL_POINT

        destination_text = extract_destination_text(original_text)

        nums = re.findall(r"-?\d+(?:\.\d+)?", destination_text)

        if len(nums) >= 2:
            req.numerical_detail = [float(nums[0]), float(nums[1])]
            req.text_detail = ""
        else:
            req.numerical_detail = []
            req.text_detail = destination_text

        return req

    req.type = CMD_TO_TYPE.get(key, PassengerRequest.UNKNOWN)

    factor = build_command_factor(original_text, req.type)

    if factor is not None:
        factor = sanitize_factor(factor)

    if factor is not None and req.type in (
        PassengerRequest.INCREASE_VELOCITY,
        PassengerRequest.DECREASE_VELOCITY,
        PassengerRequest.DRIVE_MORE_SPORTILY,
        PassengerRequest.DRIVE_MORE_COMFORTABLY,
        PassengerRequest.KEEP_MORE_DISTANCE,
    ):
        req.numerical_detail = [factor]


    return req

class TextToCommandNode(Node):

    def __init__(self):
        super().__init__('text_to_command')

        self.subscription = self.create_subscription(
            String,
            'passenger_interface/speech_to_text',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

        self.cmd_publisher = self.create_publisher(PassengerRequest, 'passenger_interface/passenger_request', 10)
        
        # Parameters
        self.declare_parameter(
            "model_name",
            "qwen3.5:4b",
        )
        self.declare_parameter(
            "ollama_base_url",
            "http://localhost:11434",
        )
        self.declare_parameter("enable_stt_correction", True)
        self.declare_parameter("simulation", False)
        self._model_name = self.get_parameter("model_name").get_parameter_value().string_value
        self._ollama_base_url = (
            self.get_parameter("ollama_base_url")
            .get_parameter_value()
            .string_value
        )
        self._simulation = self.get_parameter("simulation").get_parameter_value().bool_value
        self._enable_stt_correction = (
            self.get_parameter("enable_stt_correction")
            .get_parameter_value()
            .bool_value
        )
        self.get_logger().info(f"Simulation mode: {self._simulation}")

        self._llm_workflow = None
        if not self._simulation:
            try:
                from .text_to_command_workflow import TextToCommandWorkflow
                self._llm_workflow = TextToCommandWorkflow(
                    self._model_name,
                    self._ollama_base_url,
                    self._enable_stt_correction,
                )
                self.get_logger().info(
                    f"LLM enabled (model={self._model_name}, "
                    f"base_url={self._ollama_base_url}, "
                    f"stt_correction={self._enable_stt_correction})"
                )
            except Exception as e:
                self.get_logger().error(
                    f"Failed to initialize LLM workflow: {e}. "
                    "Commands will be rejected until the LLM is available."
                )

    def listener_callback(self, msg: String):
        self.get_logger().info(f'I heard: "{msg.data}"')

        class_key = UNKNOWN_COMMAND
        command_text = msg.data

        if self._simulation:
            class_key = simulation_classify(msg.data)
            self.get_logger().info(
                f"Simulation classification: {class_key}"
            )
        elif self._llm_workflow is not None:
            try:
                llm_out = self._llm_workflow.text_to_command(msg.data)
                corrected_text = self._llm_workflow.last_corrected_text
                command_text = corrected_text
                self.get_logger().info(
                    f'LLM-corrected transcript: "{corrected_text}"'
                )
                class_key = normalize_llm_command(llm_out)
                self.get_logger().info(
                    f"LLM output: {llm_out.strip()} "
                    f"(normalized: {class_key})"
                )
            except Exception as e:
                self.get_logger().error(
                    f"LLM call failed: {e}. Skipping command."
                )
                class_key = UNKNOWN_COMMAND
        else:
            self.get_logger().error(
                "LLM classification is unavailable; skipping command."
            )

        if class_key == UNKNOWN_COMMAND:
            self.get_logger().warn("Could not classify command; skipping publish.")
            return

        req = build_passenger_request(
            class_key=class_key,
            original_text=command_text,
            stamp_msg=self.get_clock().now().to_msg(),
        )

        if req.type == PassengerRequest.UNKNOWN:
            self.get_logger().warn(f"Mapped '{class_key}' to UNKNOWN; skipping publish.")
            return

        self.cmd_publisher.publish(req)
        self.get_logger().info(
            f"Published PassengerRequest type={req.type} num={list(req.numerical_detail)} text='{req.text_detail}'"
        )

def main(args=None):
    rclpy.init(args=args)

    text_to_command = TextToCommandNode()

    rclpy.spin(text_to_command)

    text_to_command.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
