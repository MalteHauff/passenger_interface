from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # --- Launch args ---
    number_arg = DeclareLaunchArgument(
        "number",
        default_value="5",
        description="Command number (1..21) for one-shot mode."
    )

    interactive_arg = DeclareLaunchArgument(
        "interactive",
        default_value="true",
        description="If true, run in interactive mode (read numbers from stdin)."
    )

    topic_arg = DeclareLaunchArgument(
        "topic",
        default_value="fm/speech_to_text",
        description="Topic to publish std_msgs/String on."
    )

    exit_arg = DeclareLaunchArgument(
        "exit_no",
        default_value="1",
        description="Exit number used for command 13 (leave roundabout). Ignored otherwise."
    )

    destination_arg = DeclareLaunchArgument(
        "destination",
        default_value="xyz",
        description='Destination used for command 21 (drive to ...). Ignored otherwise.'
    )
    package_name = "fm_adore_interface"
    executable_name = "simulation_node"  

    node_one_shot = Node(
        namespace="ego_vehicle",
        package=package_name,
        executable=executable_name,
        name="simulation_node_one_shot",
        output="screen",
        arguments=[
            LaunchConfiguration("number"),
            "--topic", LaunchConfiguration("topic"),
            "--exit", LaunchConfiguration("exit_no"),
            "--destination", LaunchConfiguration("destination"),
        ],
        condition=UnlessCondition(LaunchConfiguration("interactive")),
    )

    # Interactive node (reads from stdin)
    node_interactive = Node(
        namespace="ego_vehicle",
        package=package_name,
        executable=executable_name,
        name="simulation_node_interactive",
        output="screen",
        arguments=[
            "--interactive",
            "--topic", LaunchConfiguration("topic"),
            "--exit", LaunchConfiguration("exit_no"),
            "--destination", LaunchConfiguration("destination"),
        ],
        condition=IfCondition(LaunchConfiguration("interactive")),
    )

    return LaunchDescription([
        number_arg,
        interactive_arg,
        topic_arg,
        exit_arg,
        destination_arg,
        node_one_shot,
        node_interactive,
    ])
