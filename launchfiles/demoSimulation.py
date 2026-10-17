"""Launch the complete passenger voice-command interface."""

import os
from pathlib import Path
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    SetEnvironmentVariable,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def find_cuda_library_directories():
    """Return pip-installed cuBLAS and cuDNN directories for CUDA Whisper."""
    search_paths = [Path(path) for path in sys.path if path]
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        search_paths.extend(
            Path(virtual_env).glob("lib/python3*/site-packages")
        )

    directories = []
    for library in ("cublas", "cudnn"):
        for search_path in search_paths:
            library_directory = search_path / "nvidia" / library / "lib"
            if library_directory.is_dir():
                directories.append(str(library_directory))
                break

    return directories


def generate_launch_description():
    """Launch speech recognition, command interpretation, and dissemination."""
    namespace = LaunchConfiguration("namespace")
    model_name = LaunchConfiguration("model_name")
    ollama_base_url = LaunchConfiguration("ollama_base_url")
    enable_stt_correction = LaunchConfiguration("enable_stt_correction")
    simulation = LaunchConfiguration("simulation")

    whisper_model_size = LaunchConfiguration("whisper_model_size")
    whisper_device = LaunchConfiguration("whisper_device")
    whisper_compute_type = LaunchConfiguration("whisper_compute_type")
    whisper_language = LaunchConfiguration("whisper_language")
    whisper_hotwords = LaunchConfiguration("whisper_hotwords")
    audio_device = LaunchConfiguration("audio_device")
    audio_channels = LaunchConfiguration("audio_channels")
    audio_channel = LaunchConfiguration("audio_channel")
    audio_sample_rate = LaunchConfiguration("audio_sample_rate")
    end_silence_duration = LaunchConfiguration("end_silence_duration")

    default_goal_x = LaunchConfiguration("default_goal_x")
    default_goal_y = LaunchConfiguration("default_goal_y")

    source_locations_file = (
        Path(__file__).resolve().parents[1]
        / "passenger_interface"
        / "locations.json"
    )
    if source_locations_file.is_file():
        locations_file = source_locations_file
    else:
        package_share = Path(
            get_package_share_directory("passenger_interface")
        )
        locations_file = package_share / "locations.json"

    source_directory = os.environ.get("SOURCE_DIRECTORY")
    if source_directory:
        hf_cache = Path(source_directory) / ".cache" / "huggingface"
    else:
        hf_cache = Path.home() / ".cache" / "huggingface"

    return LaunchDescription([
        DeclareLaunchArgument(
            "namespace",
            default_value="ego_vehicle",
            description="Namespace shared with the simulated vehicle.",
        ),
        DeclareLaunchArgument(
            "model_name",
            default_value="qwen3.5:4b",
            description="Ollama model used for command interpretation.",
        ),
        DeclareLaunchArgument(
            "ollama_base_url",
            default_value="http://localhost:11434",
            description="Base URL of the Ollama server.",
        ),
        DeclareLaunchArgument(
            "enable_stt_correction",
            default_value="True",
            description="Correct transcripts in the Ollama request.",
        ),
        DeclareLaunchArgument(
            "simulation",
            default_value="False",
            description="Use the rule-based classifier instead of Ollama.",
        ),
        DeclareLaunchArgument(
            "whisper_model_size",
            default_value="large-v3-turbo",
        ),
        DeclareLaunchArgument(
            "whisper_device",
            default_value="cuda",
        ),
        DeclareLaunchArgument(
            "whisper_compute_type",
            default_value="float16",
        ),
        DeclareLaunchArgument(
            "whisper_language",
            default_value="de",
            description=(
                "Language code, or empty for automatic detection. "
                "Automatic detection costs an extra encoder pass."
            ),
        ),
        DeclareLaunchArgument(
            "whisper_hotwords",
            default_value=(
                "lane, roundabout, U-turn, start point, "
                "Spurwechsel, Kreisverkehr"
            ),
        ),
        DeclareLaunchArgument("audio_device", default_value="4"),
        DeclareLaunchArgument("audio_channels", default_value="4"),
        DeclareLaunchArgument("audio_channel", default_value="3"),
        DeclareLaunchArgument("audio_sample_rate", default_value="48000"),
        DeclareLaunchArgument(
            "end_silence_duration",
            default_value="1.2",
            description="Silence required before an utterance is complete.",
        ),
        DeclareLaunchArgument(
            "default_goal_x",
            default_value="606471.04",
            description="Fallback goal X coordinate for unknown named goals.",
        ),
        DeclareLaunchArgument(
            "default_goal_y",
            default_value="5797161.11",
            description="Fallback goal Y coordinate for unknown named goals.",
        ),
        SetEnvironmentVariable("HF_HOME", str(hf_cache)),
        SetEnvironmentVariable("HF_HUB_DISABLE_XET", "1"),
        SetEnvironmentVariable("HF_HUB_DOWNLOAD_TIMEOUT", "120"),
        *[
            AppendEnvironmentVariable(
                "LD_LIBRARY_PATH",
                directory,
                prepend=True,
            )
            for directory in find_cuda_library_directories()
        ],
        Node(
            package="passenger_interface",
            executable="speech_to_text",
            name="speech_to_text",
            namespace=namespace,
            output="screen",
            emulate_tty=True,
            parameters=[{
                "only_simulate": False,
                "whisper_model_size": whisper_model_size,
                "whisper_device": whisper_device,
                "whisper_compute_type": whisper_compute_type,
                "whisper_language": whisper_language,
                "whisper_hotwords": whisper_hotwords,
                "audio_device": ParameterValue(
                    audio_device,
                    value_type=int,
                ),
                "audio_channels": ParameterValue(
                    audio_channels,
                    value_type=int,
                ),
                "audio_channel": ParameterValue(
                    audio_channel,
                    value_type=int,
                ),
                "audio_sample_rate": ParameterValue(
                    audio_sample_rate,
                    value_type=int,
                ),
                "end_silence_duration": ParameterValue(
                    end_silence_duration,
                    value_type=float,
                ),
            }],
        ),
        Node(
            package="passenger_interface",
            executable="text_to_command",
            name="text_to_command",
            namespace=namespace,
            output="screen",
            emulate_tty=True,
            parameters=[{
                "simulation": ParameterValue(
                    simulation,
                    value_type=bool,
                ),
                "model_name": model_name,
                "ollama_base_url": ollama_base_url,
                "enable_stt_correction": ParameterValue(
                    enable_stt_correction,
                    value_type=bool,
                ),
            }],
        ),
        Node(
            package="passenger_interface",
            executable="command_dissemination",
            name="command_dissemination",
            namespace=namespace,
            output="screen",
            emulate_tty=True,
            parameters=[{
                "location_table_path": str(locations_file),
                "default_goal_x": ParameterValue(
                    default_goal_x,
                    value_type=float,
                ),
                "default_goal_y": ParameterValue(
                    default_goal_y,
                    value_type=float,
                ),
            }],
        ),
    ])
