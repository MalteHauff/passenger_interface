# Passenger Interface

`fm_adore_interface` is a ROS 2 passenger interface for ADORe vehicles. It
turns spoken or typed passenger requests into `PassengerRequest` messages and
forwards them to the appropriate vehicle and mission topics.

The processing pipeline consists of:

- `speech_to_text`: transcribes microphone input with Faster Whisper, or reads
  text from the terminal in simulation mode.
- `text_to_command`: classifies requests with a local Ollama model or a
  rule-based simulation fallback.
- `command_dissemination`: converts passenger requests into ADORe commands.
- `simulation_node`: publishes a set of predefined passenger commands for
  testing.

## Parameters

### Speech to text

| Parameter | Default | Description |
| --- | --- | --- |
| `only_simulate` | `false` | Read typed terminal input instead of microphone audio. |
| `whisper_model_size` | `base` | Faster Whisper model, for example `tiny.en`, `base.en`, or `small.en`. Missing models are downloaded automatically. |
| `audio_device` | `4` | Input device index; use `-1` for the system default. |
| `audio_channels` | `4` | Number of channels opened on the input device. |
| `audio_channel` | `3` | Zero-based channel used for transcription. |
| `audio_sample_rate` | `48000` | Input sample rate before conversion to 16 kHz. |

### Text to command

| Parameter | Default | Description |
| --- | --- | --- |
| `simulation` | `false` | Use rule-based classification instead of the LLM workflow. |
| `model_name` | `DLR_FM_1.llama3.3:latest` | Ollama model used when `simulation` is `false`. Ollama is expected at `http://localhost:11434`. |

### Command dissemination

| Parameter | Default | Description |
| --- | --- | --- |
| `location_table_path` | empty | Path to a JSON mapping of named destinations to `x`/`y` coordinates. |
| `default_goal_x` | `0.0` | Fallback goal x-coordinate for unknown destinations. |
| `default_goal_y` | `0.0` | Fallback goal y-coordinate for unknown destinations. |

The included `locations.json` contains example destinations. The
`demoSimulation.py` launch file exposes `simulation` and `model_name` and sets
the location table and fallback goal automatically.

## License

Eclipse Public License 2.0. See [LICENSE](LICENSE).
