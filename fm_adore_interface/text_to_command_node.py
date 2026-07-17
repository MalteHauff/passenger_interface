import rclpy
from rclpy.node import Node
from adore_ros2_msgs.msg import PassengerRequest
import re
from std_msgs.msg import String


CMD_TO_TYPE = {
    "perform emergency stop": PassengerRequest.EXECUTE_EMERGENCY_STOP,
    "follow_lane": PassengerRequest.EXECUTE_LANE_FOLLOWING,
    "change_lane_left": PassengerRequest.EXECUTE_LANE_CHANGE_LEFT,
    "change_lane_right": PassengerRequest.EXECUTE_LANE_CHANGE_RIGHT,
    "drive faster": PassengerRequest.INCREASE_VELOCITY,
    "slow down": PassengerRequest.DECREASE_VELOCITY,
    "stop and let someone board": PassengerRequest.STOP_AND_LET_SB_BOARD,
    "stop and let me exit": PassengerRequest.STOP_AND_LET_SB_EXIT,
    "stop and park": PassengerRequest.STOP_AND_PARK,
    "stay behind the vehicle ahead": PassengerRequest.STAY_BEHIND_THE_VEHICLE_AHEAD,
    "turn right": PassengerRequest.TURN_RIGHT,
    "turn left": PassengerRequest.TURN_LEFT,
    "perform u-turn": PassengerRequest.PERFORM_U_TURN,
    "cross junction straight": PassengerRequest.CROSS_JUNCTION_STRAIGHT,
    "drive back to start point": PassengerRequest.DRIVE_BACK_TO_START_POINT,
    "accelerate more gently": PassengerRequest.DRIVE_MORE_COMFORTABLY,
    "drive sportier": PassengerRequest.DRIVE_MORE_SPORTILY,
    "resume ride": PassengerRequest.RESUME_RIDE,
    "keep more distance": PassengerRequest.KEEP_MORE_DISTANCE,
    "leave roundabout at x-th exit": PassengerRequest.LEAVE_ROUNDABOUT_AT_EXIT_X,
    "drive to xyz": PassengerRequest.SET_NEW_GOAL_POINT,
}
def fallback_classify(text: str) -> str:
    t = text.lower().strip()

    if "emergency" in t or "stop immediately" in t:
        return "perform emergency stop"
    if "follow" in t or "straight" in t:
        return "follow_lane"
    if "faster" in t or "speed up" in t or "accelerate" in t:
        return "drive faster"
    if "slower" in t or "slow down" in t:
        return "slow down"
    if "change lane right" in t or ("right lane" in t and "change" in t):
        return "change_lane_right"
    if "change lane left" in t or ("left lane" in t and "change" in t):
        return "change_lane_left"
    if "turn right" in t:
        return "turn right"
    if "turn left" in t:
        return "turn left"
    if "u-turn" in t or "turn around" in t:
        return "perform u-turn"
    if "park" in t:
        return "stop and park"
    if "board" in t or "pick up" in t:
        return "stop and let someone board"
    if "let me out" in t or "exit" in t:
        return "stop and let me exit"
    if "distance" in t:
        return "keep more distance"
    if "resume" in t or "continue ride" in t:
        return "resume ride"
    if "roundabout" in t or "exit" in t:
        return "leave roundabout at x-th exit"
    if "drive back to start point" in t or "go back to start point" in t:
        return "drive back to start point"
    if "drive to" in t or "go to" in t:
        return "drive to xyz"

    return "unknown"

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


def normalize_llm_command(cmd_string: str) -> str:
    """
    Turns e.g. "4. change_lane_right: Go to the right lane."
    into a stable key we can map on.
    """
    s = cmd_string.strip()

    # remove optional leading "N." (e.g., "4.")
    s = re.sub(r"^\s*\d+\.\s*", "", s)

    # take only the left part before the description
    s = s.split(":", 1)[0].strip().lower()

    return s

def build_passenger_request(class_key: str, original_text: str, stamp_msg) -> PassengerRequest:
    req = PassengerRequest()
    req.header.stamp = stamp_msg
    req.numerical_detail = []
    req.text_detail = ""

    key = class_key.lower().strip()

    # roundabout exit number extraction
    if "leave roundabout" in key:
        req.type = PassengerRequest.LEAVE_ROUNDABOUT_AT_EXIT_X
        m = re.search(r"(\d+)", original_text)
        exit_no = float(m.group(1)) if m else 1.0
        req.numerical_detail = [exit_no]
        return req

    # destination extraction: "drive to X" / "go to X"
    if key.startswith("drive to") or key.startswith("go to") or "drive to xyz" == key:
        req.type = PassengerRequest.SET_NEW_GOAL_POINT

        m = re.search(r"(?:drive to|go to)\s+(.+)$", original_text, flags=re.IGNORECASE)
        destination_text = m.group(1).strip() if m else ""

        nums = re.findall(r"-?\d+(?:\.\d+)?", destination_text)

        if len(nums) >= 2:
            req.numerical_detail = [float(nums[0]), float(nums[1])]
            req.text_detail = ""
        else:
            req.numerical_detail = []
            req.text_detail = destination_text.lower().strip()

        return req

    req.type = CMD_TO_TYPE.get(key, PassengerRequest.UNKNOWN)
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
            'fm/speech_to_text',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

        self.cmd_publisher = self.create_publisher(PassengerRequest, 'fm/passenger_request', 10)
        
        # Parameters
        self.declare_parameter("model_name","DLR_FM_1.llama3.3:latest")
        self.declare_parameter("simulation", False)
        self._model_name = self.get_parameter("model_name").get_parameter_value().string_value
        self._simulation = self.get_parameter("simulation").get_parameter_value().bool_value
        self.get_logger().info(f"Simulation mode: {self._simulation}")

        self._llm_workflow = None
        if not self._simulation:
            try:
                from .text_to_command_workflow import TextToCommandWorkflow
                self._llm_workflow = TextToCommandWorkflow(self._model_name)
                self.get_logger().info(f"LLM enabled (model={self._model_name})")
            except Exception as e:
                self.get_logger().error(f"Failed to initialize LLM workflow: {e}. Falling back to hardcoded mode.")
                self._simulation = True

    def listener_callback(self, msg: String):
        self.get_logger().info(f'I heard: "{msg.data}"')

        class_key = None

        if not self._simulation and self._llm_workflow is not None:
            try:
                llm_out = self._llm_workflow.text_to_command(msg.data)
                # Normalize if your LLM returns "4. change_lane_right: ..."
                class_key = llm_out.strip()
                self.get_logger().info(f"LLM output: {class_key}")
            except Exception as e:
                self.get_logger().error(f"LLM call failed: {e}. Using hardcoded fallback.")
                class_key = None

        if class_key is None:
            class_key = fallback_classify(msg.data)

        if class_key == "unknown":
            self.get_logger().warn("Could not classify command; skipping publish.")
            return

        req = build_passenger_request(
            class_key=class_key,
            original_text=msg.data,
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