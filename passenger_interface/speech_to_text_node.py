import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import sounddevice
import numpy as numpy
import queue
import threading
from faster_whisper import WhisperModel
from huggingface_hub.utils import (
    LocalEntryNotFoundError
)
import sys
import time
from scipy.signal import resample_poly

from .speech_to_text_utils import (
    calculate_blocksize,
    calculate_rms,
    is_meaningful_transcript,
    UtteranceBuffer,
)


try:
    import tty
    import termios
except ImportError:
    termios = None


SAMPLE_RATE = 16000
AUDIO_CHUNK_DURATION = 0.1
END_SILENCE_DURATION = 0.7
PRE_ROLL_DURATION = 0.3
MAX_UTTERANCE_DURATION = 8.0
MIN_AUDIO_RMS = 0.005
MAX_NO_SPEECH_PROBABILITY = 0.6
WHISPER_MODEL_SIZE = "large-v3-turbo"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_LANGUAGE = ""
WHISPER_HOTWORDS = (
    "lane, roundabout, U-turn, start point, Spurwechsel, Kreisverkehr"
)


class SpeechToTextNode(Node):

    def __init__(self):
        super().__init__('speech_to_text')
        
        self.publisher = self.create_publisher(String, 'passenger_interface/speech_to_text', 10)
        self.running = True

        self.declare_parameter("whisper_model_size", WHISPER_MODEL_SIZE)
        self.declare_parameter("whisper_device", WHISPER_DEVICE)
        self.declare_parameter(
            "whisper_compute_type",
            WHISPER_COMPUTE_TYPE,
        )
        self.declare_parameter("whisper_language", WHISPER_LANGUAGE)
        self.declare_parameter("whisper_hotwords", WHISPER_HOTWORDS)

        self.whisper_model_size = (
            self.get_parameter("whisper_model_size")
            .get_parameter_value()
            .string_value
        )
        self.whisper_device = (
            self.get_parameter("whisper_device")
            .get_parameter_value()
            .string_value
        )
        self.whisper_compute_type = (
            self.get_parameter("whisper_compute_type")
            .get_parameter_value()
            .string_value
        )
        self.whisper_language = (
            self.get_parameter("whisper_language")
            .get_parameter_value()
            .string_value
            .strip()
        )
        self.whisper_hotwords = (
            self.get_parameter("whisper_hotwords")
            .get_parameter_value()
            .string_value
            .strip()
        )
        
        # simulation mode: use keyboard input as simulated speech.
        self.declare_parameter("only_simulate",False)
        self.only_simulate = self.get_parameter("only_simulate").get_parameter_value().bool_value
        if self.only_simulate:
            self.get_logger().warning("Simulation Mode active!")
            self.read_keyboard_thread = threading.Thread(target=self.read_keyboard, daemon=True)
            self.get_logger().info("Type text in the terminal and press Enter to publish it as simulated speech input.")
            self.read_keyboard_thread.start()
            return

        self.get_logger().info(
            "Whisper settings: "
            f"model={self.whisper_model_size}, "
            f"device={self.whisper_device}, "
            f"compute_type={self.whisper_compute_type}, "
            f"language={self.whisper_language or 'auto'}"
        )

        try:
            self.get_logger().info(
                f"Attempting to load '{self.whisper_model_size}' model "
                "from local cache..."
            )
            self.model = WhisperModel(
                self.whisper_model_size,
                device=self.whisper_device,
                compute_type=self.whisper_compute_type,
                local_files_only=True
            )
            self.get_logger().info("Model loaded successfully from local files.")

        except (LocalEntryNotFoundError, RuntimeError) as e:
            self.get_logger().error(
                f"Model '{self.whisper_model_size}' not found in local cache. "
            )
            self.get_logger().info(
                f"Attempting to load '{self.whisper_model_size}' model "
                "from the internet..."
            )
            self.model = WhisperModel(
                self.whisper_model_size,
                device=self.whisper_device,
                compute_type=self.whisper_compute_type,
                local_files_only=False
            )
            self.get_logger().info("Model loaded successfully from the internet.")

        self.declare_parameter("audio_device", 4)
        self.declare_parameter("audio_channels", 4)
        self.declare_parameter("audio_channel", 3)
        self.declare_parameter("audio_sample_rate", 48000)
        self.declare_parameter(
            "audio_chunk_duration",
            AUDIO_CHUNK_DURATION,
        )
        self.declare_parameter(
            "end_silence_duration",
            END_SILENCE_DURATION,
        )
        self.declare_parameter("pre_roll_duration", PRE_ROLL_DURATION)
        self.declare_parameter(
            "max_utterance_duration",
            MAX_UTTERANCE_DURATION,
        )
        self.declare_parameter("min_audio_rms", MIN_AUDIO_RMS)
        self.declare_parameter(
            "max_no_speech_probability",
            MAX_NO_SPEECH_PROBABILITY,
        )
        self.declare_parameter("vad_filter", True)
    
        self.audio_device = (
            self.get_parameter("audio_device")
            .get_parameter_value()
            .integer_value
        )

        self.audio_channels = (
            self.get_parameter("audio_channels")
            .get_parameter_value()
            .integer_value
        )

        self.audio_channel = (
            self.get_parameter("audio_channel")
            .get_parameter_value()
            .integer_value
        )

        self.audio_sample_rate = (
            self.get_parameter("audio_sample_rate")
            .get_parameter_value()
            .integer_value
        )

        self.audio_chunk_duration = (
            self.get_parameter("audio_chunk_duration")
            .get_parameter_value()
            .double_value
        )

        self.end_silence_duration = (
            self.get_parameter("end_silence_duration")
            .get_parameter_value()
            .double_value
        )

        self.pre_roll_duration = (
            self.get_parameter("pre_roll_duration")
            .get_parameter_value()
            .double_value
        )

        self.max_utterance_duration = (
            self.get_parameter("max_utterance_duration")
            .get_parameter_value()
            .double_value
        )

        self.min_audio_rms = (
            self.get_parameter("min_audio_rms")
            .get_parameter_value()
            .double_value
        )

        self.max_no_speech_probability = (
            self.get_parameter("max_no_speech_probability")
            .get_parameter_value()
            .double_value
        )

        self.vad_filter = (
            self.get_parameter("vad_filter")
            .get_parameter_value()
            .bool_value
        )

        self.get_logger().info("sound devices:")
        self.get_logger().info(str(sounddevice.query_devices()))
        audio_device = None if self.audio_device == -1 else self.audio_device
        self.audio_queue = queue.Queue()
        device_info = sounddevice.query_devices(audio_device, 'input')
        self._validate_audio_settings(device_info)
        sounddevice.check_input_settings(
            device=audio_device,
            channels=self.audio_channels,
            dtype="float32",
            samplerate=self.audio_sample_rate,
        )
        self.get_logger().info(
            f"Using audio input device: {device_info}"
        )
        self.get_logger().info(
            "Audio settings: "
            f"{self.audio_sample_rate} Hz, {self.audio_channels} channels, "
            f"selected channel {self.audio_channel}, "
            f"{self.audio_chunk_duration:.2f} second capture chunks"
        )
        self.get_logger().info(
            "Utterance detection: "
            f"{self.end_silence_duration:.1f} seconds end silence, "
            f"{self.pre_roll_duration:.1f} seconds pre-roll, "
            f"{self.max_utterance_duration:.1f} seconds maximum"
        )

        self.stream = sounddevice.InputStream(
            samplerate=self.audio_sample_rate, 
            channels=self.audio_channels, 
            dtype="float32",
            device=audio_device,
            blocksize=calculate_blocksize(
                self.audio_sample_rate,
                self.audio_chunk_duration,
            ),
            callback=self.audio_callback
        )
        self.processing_thread = threading.Thread(target=self.process_audio)
        
        self.get_logger().info("Starting audio stream and processing thread...")
        self.stream.start()
        self.processing_thread.start()

    def _validate_audio_settings(self, device_info):
        if self.audio_chunk_duration <= 0.0:
            raise ValueError(
                "audio_chunk_duration must be greater than zero"
            )

        if self.end_silence_duration <= 0.0:
            raise ValueError(
                "end_silence_duration must be greater than zero"
            )

        if self.pre_roll_duration < 0.0:
            raise ValueError("pre_roll_duration must not be negative")

        if self.max_utterance_duration <= self.audio_chunk_duration:
            raise ValueError(
                "max_utterance_duration must be longer than "
                "audio_chunk_duration"
            )

        if self.audio_channels <= 0:
            raise ValueError("audio_channels must be greater than zero")

        max_input_channels = int(device_info["max_input_channels"])
        if self.audio_channels > max_input_channels:
            raise ValueError(
                f"audio_channels is {self.audio_channels}, but the selected "
                f"device supports only {max_input_channels} input channels"
            )

        if not 0 <= self.audio_channel < self.audio_channels:
            raise ValueError(
                f"audio_channel must be between 0 and "
                f"{self.audio_channels - 1}; got {self.audio_channel}"
            )

        if self.min_audio_rms < 0.0:
            raise ValueError("min_audio_rms must not be negative")

        if not 0.0 <= self.max_no_speech_probability <= 1.0:
            raise ValueError(
                "max_no_speech_probability must be between 0 and 1"
            )

    def audio_callback(self, indata, frames, time, status):
        if status:
            self.get_logger().warning(str(status))
        # Just put the raw audio data into the queue
        self.audio_queue.put(indata[:, self.audio_channel].copy())

    def publish_string(self, text, log = False):
        msg = String()
        msg.data = text
        self.publisher.publish(msg)
        if log:
            self.get_logger().info(f'Published: "{msg.data}"')

    def process_audio(self):
        self.get_logger().info("Audio processing thread started.")
        utterance_buffer = UtteranceBuffer(
            sample_rate=self.audio_sample_rate,
            chunk_duration=self.audio_chunk_duration,
            pre_roll_duration=self.pre_roll_duration,
            end_silence_duration=self.end_silence_duration,
            max_utterance_duration=self.max_utterance_duration,
        )
        last_level_log = 0.0

        while self.running:
            try:
                audio = self.audio_queue.get(timeout=1)

                audio_rms = calculate_rms(audio)
                now = time.monotonic()
                if now - last_level_log >= 1.0:
                    self.get_logger().debug(
                        f"Selected-channel audio RMS: {audio_rms:.5f}"
                    )
                    last_level_log = now

                contains_speech = audio_rms >= self.min_audio_rms
                completed_audio, speech_started = utterance_buffer.add(
                    audio,
                    contains_speech,
                )
                if speech_started:
                    self.get_logger().debug(
                        f"Speech started (RMS={audio_rms:.5f})"
                    )

                if completed_audio is None:
                    continue

                self.get_logger().debug(
                    "Transcribing "
                    f"{completed_audio.size / self.audio_sample_rate:.2f} "
                    "seconds of buffered audio"
                )

                self.transcribe_audio(completed_audio)

            except queue.Empty:
                # This is normal if there's silence
                continue
            except Exception as e:
                self.get_logger().error(f"Error in processing thread: {e}")

    def transcribe_audio(self, audio):
        audio_16k = resample_poly(
                audio,
                SAMPLE_RATE,
                self.audio_sample_rate,
            ).astype("float32")
        segments, _ = self.model.transcribe(
            audio_16k,
            language=self.whisper_language or None,
            task="transcribe",
            beam_size=3,
            temperature=0,
            vad_filter=self.vad_filter,
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
            condition_on_previous_text=False,
            hotwords=self.whisper_hotwords or None,
        )

        accepted_segments = (
            segment.text
            for segment in segments
            if segment.no_speech_prob
            <= self.max_no_speech_probability
        )
        text = "".join(accepted_segments).strip()

        if is_meaningful_transcript(text) and self.running:
            self.publish_string(text, True)
    
    def read_keyboard(self):
        while rclpy.ok():
            try:
                # blocking
                line = sys.stdin.readline()

                
                if not line or not self.running:
                    break

                # Strip trailing newline characters
                text = line.strip()

                if text: # Don't publish empty strings
                    self.publish_string(text,True)

            except Exception as e:
                if self.running:
                    self.get_logger().error(f"Error reading keyboard input: {e}")
                    self.get_logger().error("Retry")

    def destroy_node(self):
        self.get_logger().info("Shutting down...")
        self.running = False  # Signal the thread to stop
        if not self.only_simulate:
            self.stream.stop()
            self.stream.close()
            self.processing_thread.join() 
        else:
            self.read_keyboard_thread.join(timeout=1.0) # Wait for the thread to finish
        super().destroy_node()
        

def main(args=None):
    rclpy.init(args=args)

    speech_to_text_node = SpeechToTextNode()

    try:
        rclpy.spin(speech_to_text_node)
    except KeyboardInterrupt:
        pass
    finally:
        speech_to_text_node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
