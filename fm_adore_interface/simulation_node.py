
import sys
import argparse
import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from std_msgs.msg import String
import re


COMMAND_TEXT = {
    1:  "perform emergency stop: Stop as soon and quickly as possible.",
    2:  "follow_lane: Continue on the same lane, without junctions.",
    3:  "change_lane_left: Go to the left lane.",
    4:  "change_lane_right: Go to the right lane.",
    5:  "drive faster: Increase the velocity.",
    6:  "slow down: Decrease the velocity.",
    7:  "stop and let someone board: Stop the vehicle in order to let somebody board.",
    8:  "stop and let me exit: Stop the vehicle in order to let somebody exit.",
    9:  "stop and park: Stop and park the vehicle without letting passengers in or out.",
    10: "stay behind the vehicle ahead: Do not overtake the vehicle ahead and stay in lane behind it.",
    11: "turn right: Turn to the right.",
    12: "perform u-turn: Perform a u-turn at the next possibility.",
    13: "leave roundabout at {exit_no}-th exit: Exit the roundabout at the specified exit.",
    14: "cross junction straight: Continue on the same road through the next junction.",
    15: "turn left: Turn to the left.",
    16: "drive back to start point: Change the destination to the starting point.",
    17: "accelerate more gently: Do not allow high acceleration values.",
    18: "drive sportier: Allow higher acceleration values.",
    19: "resume ride: Continue the ride.",
    20: "keep more distance: Keep more distance to other vehicles.",
    21: "drive to {destination}: Set destination to {destination}.",
}


def build_command_text(n: int, exit_no: int | None, destination ) -> str:
    if n not in COMMAND_TEXT:
        raise ValueError(f"Command number must be in 1..21, got {n}")

    template = COMMAND_TEXT[n]
    logger = rclpy.logging.get_logger("number_to_text_publisher")
    if n == 13:
        if exit_no is None:
            exit_no = 1  # default if not provided
        return template.format(exit_no=exit_no)
    if n == 21:
        if destination is None:
            logger.warning("No destination provided for command 21, using default 'xyz'.")
            destination = "xyz"  # default if not provided
        logger.info(f"Using destination '{destination}' for command 21.")
        return template.format(destination=destination)

    return template


class NumberToTextPublisher(Node):
    def __init__(self, topic: str):
        super().__init__('number_to_text_publisher')
        self._topic = topic
        self._pub = self.create_publisher(String, self._topic, 10)

    def wait_for_subscriber(self, timeout_sec: float = 2.0) -> None:
        
        end_time = self.get_clock().now().nanoseconds / 1e9 + timeout_sec
        while rclpy.ok() and self._pub.get_subscription_count() == 0:
            now = self.get_clock().now().nanoseconds / 1e9
            if now >= end_time:
                break
            rclpy.spin_once(self, timeout_sec=0.1)

    def publish_text(self, text: str) -> None:
        msg = String()
        msg.data = text
        self._pub.publish(msg)
        self.get_logger().info(f'Published on "{self._topic}": "{text}"')


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="number_to_text_publisher",
        description="Publish a mapped command text (1..21) to fm/speech_to_text."
    )
    parser.add_argument("number", nargs="?", type=int, help="Command number (1..21)")
    parser.add_argument("--topic", default="fm/speech_to_text", help="Output topic (std_msgs/String)")
    parser.add_argument("--interactive", action="store_true", help="Read numbers in a loop from stdin")
    parser.add_argument("--exit", dest="exit_no", type=int, default=None, help="Exit number for command 13")
    parser.add_argument("--destination", type=str, default=None, help='Destination for command 21 (e.g. "home")')
    return parser.parse_args(argv)

def ask_change_percentage(command_no: int) -> str:
    percentage_commands = {
        5: "velocity increase",
        6: "velocity decrease",
        17: "acceleration decrease",
        18: "acceleration increase",
    }

    if command_no not in percentage_commands:
        return ""

    value = input(
        f"percentage for {percentage_commands[command_no]} "
        f"(e.g. 20 for 20%, empty = default): "
    ).strip()

    if not value:
        return ""

    return f" by {value} percent"

def interactive_loop(node: NumberToTextPublisher, args: argparse.Namespace) -> None:
    node.get_logger().info("Interactive mode. Enter 1..21 (or 'q' to quit).")
    while rclpy.ok():
        try:
            s = input("command number (1..21, q=quit): ").strip()
            node.get_logger().info(f"Input: {s}")

            if s.lower() in ("q", "quit", "exit"):
                break

            n = int(s)
            node.get_logger().info(f"Received command number: {n}")

            # exit_no = args.exit_no
            # des = args.destination
            # nums = re.findall(r"-?\d+(?:\.\d+)?", des) if des is not None else []
            # destination = [float(n) for n in nums] if nums else None

            # if n == 13 and exit_no is None:
            #     exit_no = int(input("roundabout exit number: ").strip())
            # if n == 21 and destination is None:
            #     destination = input("destination: ").strip()
            exit_no = args.exit_no
            destination = args.destination

            if n == 13 and exit_no is None:
                exit_no = int(input("roundabout exit number: ").strip())

            if n == 21 and destination is None:
                destination = input("go to destination, e.g. 'airport' or '10.0 5.0': ").strip()
            text = build_command_text(n, exit_no=exit_no, destination=destination)

            percentage_text = ask_change_percentage(n)
            text += percentage_text

            node.wait_for_subscriber()
            node.publish_text(text)
            rclpy.spin_once(node, timeout_sec=0.1)

        except Exception as e:
            node.get_logger().error(str(e))


def main(args=None):
    rclpy.init(args=args)

    non_ros_argv = remove_ros_args(args if args is not None else sys.argv)

    cli = parse_args(non_ros_argv[1:])

    node = NumberToTextPublisher(topic=cli.topic)

    try:
        if cli.interactive:
            interactive_loop(node, cli)
        else:
            if cli.number is None:
                raise ValueError("Missing command number. Example: ... number_to_text_publisher 5")
            text = build_command_text(cli.number, exit_no=cli.exit_no, destination=cli.destination)
            node.wait_for_subscriber()
            node.publish_text(text)
            # Spin briefly so the message has time to flush
            rclpy.spin_once(node, timeout_sec=0.2)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
