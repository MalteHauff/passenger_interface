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
from scipy.signal import resample_poly


try:
    import tty
    import termios
except ImportError:
    termios = None


BLOCK_DURATION = 3
SAMPLE_RATE = 16000


class SpeechToTextNode(Node):

    def __init__(self):
        super().__init__('speech_to_text')
        
        self.publisher = self.create_publisher(String, 'fm/speech_to_text', 10)
        self.running = True

        self.declare_parameter("whisper_model_size","base")
        model_size = self.get_parameter("whisper_model_size").get_parameter_value().string_value
        
        # simulation mode: use keyboard input as simulated speech.
        self.declare_parameter("only_simulate",False)
        self.only_simulate = self.get_parameter("only_simulate").get_parameter_value().bool_value
        if self.only_simulate:
            self.get_logger().warning("Simulation Mode active!")
            self.read_keyboard_thread = threading.Thread(target=self.read_keyboard, daemon=True)
            self.get_logger().info("Type text in the terminal and press Enter to publish it as simulated speech input.")
            self.read_keyboard_thread.start()
            return

        try:
            self.get_logger().info(f"Attempting to load '{model_size}' model from local cache...")
            self.model = WhisperModel(
                model_size, 
                device="cpu", 
                compute_type="int8",
                local_files_only=True
            )
            self.get_logger().info("Model loaded successfully from local files.")

        except (LocalEntryNotFoundError, RuntimeError) as e:
            self.get_logger().error(
                f"Model '{model_size}' not found in local cache. "
            )
            self.get_logger().info(f"Attempting to load '{model_size}' model from the internet...")
            self.model = WhisperModel(
                model_size, 
                device="cpu", 
                compute_type="int8",
                local_files_only=False
            )
            self.get_logger().info("Model loaded successfully from the internet.")

        self.declare_parameter("audio_device", 4)
        self.declare_parameter("audio_channels", 4)
        self.declare_parameter("audio_channel", 3)
        self.declare_parameter("audio_sample_rate", 48000)
    
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
        self.get_logger().info("sound devices:")
        self.get_logger().info(str(sounddevice.query_devices()))
        # self.declare_parameter("audio_device", -1)
        audio_device_index = self.get_parameter("audio_device").get_parameter_value().integer_value
        audio_device = None if audio_device_index == -1 else audio_device_index
        self.audio_queue = queue.Queue()
        device_info = sounddevice.query_devices(audio_device, 'input')
        self.get_logger().info(
            f"Using audio input device: {device_info}"
        )

        self.stream = sounddevice.InputStream(
            samplerate=self.audio_sample_rate, 
            channels=self.audio_channels, 
            dtype="float32",
            device=audio_device,
            blocksize=int(SAMPLE_RATE * BLOCK_DURATION), 
            callback=self.audio_callback
        )
        self.processing_thread = threading.Thread(target=self.process_audio)
        
        self.get_logger().info("Starting audio stream and processing thread...")
        self.stream.start()
        self.processing_thread.start()
    
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
        while self.running:
            try:
                # Wait for a new audio chunk from the queue
                audio = self.audio_queue.get(timeout=1)
                
                #audio_16k = librosa.resample(audio, orig_sr=48000, target_sr=16000)
                audio_16k = resample_poly(
                        audio,
                        SAMPLE_RATE,             # 16000
                        self.audio_sample_rate,  # 48000
                    ).astype("float32")
                # Perform the slow transcription
                segments, _ = self.model.transcribe(audio_16k, language='en')
                
                # Combine transcribed segments into a single string
                text = "".join(segment.text for segment in segments).strip()

                if text and self.running: # Only publish if text was transcribed and node still running
                    self.publish_string(text,True)

            except queue.Empty:
                # This is normal if there's silence
                continue
            except Exception as e:
                self.get_logger().error(f"Error in processing thread: {e}")
    
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