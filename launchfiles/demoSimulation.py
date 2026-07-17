# from launch import LaunchDescription
# from launch_ros.actions import Node

# import os
# import sys
# from pathlib import Path


# workspace_src = Path(__file__).resolve().parents[3]

# scenarios_root = workspace_src / "adore_scenarios" / "simulation_scenarios"

# print(f"Using scenarios root: {scenarios_root}")


# def find_file_parent(root: Path, filename: str) -> Path:
#     matches = list(root.rglob(filename))
#     if not matches:
#         raise FileNotFoundError(f"Could not find {filename} below {root}")
#     return matches[0].parent


# simulated_vehicle_dir = find_file_parent(scenarios_root, "simulated_vehicle.py")
# visualizer_dir = find_file_parent(scenarios_root, "visualizer.py")

# print(f"Using simulated_vehicle helper dir: {simulated_vehicle_dir}")
# print(f"Using visualizer helper dir: {visualizer_dir}")

# for helper_dir in [simulated_vehicle_dir, visualizer_dir]:
#     helper_dir = str(helper_dir)
#     if helper_dir not in sys.path:
#         sys.path.insert(0, helper_dir)


# from simulated_vehicle import create_simulated_vehicle
# from visualizer import create_visualizer


# start_pose = (606450.2677, 5797277.124, 1.5)
# goal_position = (606528.44, 5797310.56)


# def generate_launch_description():
#     map_image_folder = scenarios_root / "assets" / "maps"
#     map_folder = scenarios_root / "assets" / "tracks"
#     vehicle_param = scenarios_root / "assets" / "vehicle_params"

#     map_file = map_folder / "de_bs_borders_wfs.r2sr"
#     vehicle_model_file = vehicle_param / "NGC.json"

#     interface_python_dir = Path(__file__).resolve().parents[1] / "fm_adore_interface"
#     locations_file = interface_python_dir / "locations.json"

#     print(f"Using map file: {map_file}")
#     print(f"Using vehicle model file: {vehicle_model_file}")
#     print(f"Using locations file: {locations_file}")

#     return LaunchDescription([
#         *create_simulated_vehicle(
#             namespace="ego_vehicle",
#             start_pose_utm=start_pose,
#             goal_position_utm=goal_position,
#             vehicle_id=111,
#             v2x_id=0,
#         ),

#         *create_visualizer(
#             whitelist=["ego_vehicle"],
#             visualization_offset=start_pose,
#         ),

#         Node(
#             package="fm_adore_interface",
#             executable="text_to_command",
#             name="text_to_command",
#             namespace="ego_vehicle",
#             output="screen",
#             emulate_tty=True,
#             parameters=[
#                 {"simulation": True},
#             ],
#         ),

#         Node(
#             package="fm_adore_interface",
#             executable="command_dissemination",
#             name="command_dissemination",
#             namespace="ego_vehicle",
#             output="screen",
#             emulate_tty=True,
#             parameters=[
#                 {
#                     "location_table_path": str(locations_file),
#                     "default_goal_x": goal_position[0],
#                     "default_goal_y": goal_position[1],
#                 }
#             ],
#         ),
#     ])


from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from pathlib import Path


start_pose = (606450.2677, 5797277.124, 1.5)
goal_position = (606528.44, 5797310.56)


def generate_launch_description():
    interface_python_dir = Path(__file__).resolve().parents[1] / "fm_adore_interface"
    locations_file = interface_python_dir / "locations.json"
    model_name = LaunchConfiguration("model_name", default="DLR_FM_1.llama3.3:latest")
    simulation = LaunchConfiguration("simulation", default="False")
    print(f"Using locations file: {locations_file}")

    return LaunchDescription([
        DeclareLaunchArgument(
            "model_name",
            default_value="llama3.2:latest",
            description="Name of the LLM model to use for text-to-command conversion.",
        ),
        DeclareLaunchArgument(
            "simulation",
            default_value="False",
            description="Whether to run in simulation mode (True) or with LLM (False).",
        ),


        Node(
            package="fm_adore_interface",
            executable="text_to_command",
            name="text_to_command",
            namespace="ego_vehicle",
            output="screen",
            emulate_tty=True,
            parameters=[
                {"simulation": simulation,
                "model_name": model_name,
                }
            ],
        ),

        Node(
            package="fm_adore_interface",
            executable="command_dissemination",
            name="command_dissemination",
            namespace="ego_vehicle",
            output="screen",
            emulate_tty=True,
            parameters=[
                {
                    "location_table_path": str(locations_file),
                    "default_goal_x": goal_position[0],
                    "default_goal_y": goal_position[1],
                }
            ],
        ),
    ])