from launch import LaunchDescription
from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode
import os
import sys
base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),"adore_scenarios")
print(base_dir)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
from scenario_helpers.simulated_vehicle import create_simulated_vehicle_nodes
from scenario_helpers.simulated_vehicle import Position
from scenario_helpers.visualizer import create_visualization_nodes

start_position = Position(utm=(606450.2677, 5797277.124, 32, 'N'), psi=1.5)
goal_position = Position(utm=(606528.44, 5797310.56, 32, 'N'))

def generate_launch_description():
    launch_file_dir = os.path.dirname(os.path.realpath(__file__))
    map_image_folder = os.path.abspath(os.path.join(launch_file_dir, "../../../../adore_scenarios/assets/maps/"))
    map_folder = os.path.abspath(os.path.join(launch_file_dir, "../../../../adore_scenarios/assets/tracks/"))
    vehicle_param = os.path.abspath(os.path.join(launch_file_dir, "../../../../adore_scenarios/assets/vehicle_params/"))
    map_file = map_folder + "/de_bs_borders_wfs.r2sr"
    vehicle_model_file = vehicle_param + "/NGC.json"
    
    return LaunchDescription([
        #*create_visualization_nodes(
        #    whitelist=["ego_vehicle"],
        #    asset_folder=map_image_folder,
        #    use_center_ego=True
        #),
        *create_simulated_vehicle_nodes(
            namespace="ego_vehicle",
            start_position=start_position,
            goal_position=goal_position,
            map_file=map_file,
            model_file=vehicle_model_file,
            controllable=True,
            v2x_id=0,
            vehicle_id=0,
            controller=1,
            debug=False
        ),
        Node(
                package="fm_adore_interface",
                executable="speech_to_text",
                name="speech_to_text",
                namespace="ego_vehicle",
                output='screen', 
                # Tensure output appearing immediately
                emulate_tty=True, 
                #prefix="xterm -e ", # xhost +local:
                parameters=[
                    {'whisper_model_size': 'base.en'},
                    {'only_simulate': False},
                ]
            ),
            Node(
                package="fm_adore_interface",
                executable="text_to_command",
                name="text_to_command",
                namespace="ego_vehicle",
                output='screen', 
                # Tensure output appearing immediately
                emulate_tty=True, 
                #prefix="xterm -e ", # xhost +local:
                parameters=[
                    {'whisper_model_size': 'tiny.en'},
                    {'only_simulate': True},
                ]
            ),
            Node(
                package="fm_adore_interface",
                executable="command_dissemination",
                name="command_dissemination",
                namespace="ego_vehicle",
                output='screen', 
                # Tensure output appearing immediately
                emulate_tty=True, 
                #prefix="xterm -e ", # xhost +local:
                parameters=[
                ]
            ),
    ])
