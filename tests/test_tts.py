"""Simple Piper TTS test script."""

import wave
from pathlib import Path
from piper.voice import PiperVoice

# Paths
MODEL_PATH = Path(__file__).parent / "models" / "tts" / "en_US-lessac-medium.onnx"
OUTPUT_PATH = Path(__file__).parent / "output.wav"

# Text to synthesize
text = "Hello! This is a test of Piper text-to-speech. Piper is an open-source, offline voice synthesis system."

# Load the voice model
print(f"Loading model from {MODEL_PATH}...")
voice = PiperVoice.load(str(MODEL_PATH))

# Synthesize speech directly to WAV file
print(f"Synthesizing speech...")
with wave.open(str(OUTPUT_PATH), 'wb') as wav_file:
    voice.synthesize_wav(text, wav_file)

print(f"✓ Audio saved to {OUTPUT_PATH}")
print(f"  Sample rate: {voice.config.sample_rate} Hz")
print(f"Done!")
