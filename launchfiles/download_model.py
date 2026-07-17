
# english: "tiny.en", "base.en", "small.en", "medium.en"
# multilingual: "tiny", "base", "small", "medium"
from faster_whisper import WhisperModel
MODEL_SIZE = "base" 

print(f"Downloading and caching model: {MODEL_SIZE}")

model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

print("Model download complete and cached successfully!")