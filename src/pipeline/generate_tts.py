"""Generate TTS audio files for chemical compound names using Gemini 2.5 Flash TTS."""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
import wave
import time

load_dotenv()

# Paths
COMPOUNDS_FILE = Path(__file__).parent.parent / "data" / "compounds.json"

# Initialize Gemini client
api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Helper function to save wave file
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

# Load all compounds from single JSON file
print(f"Loading compounds from {COMPOUNDS_FILE}...")
with open(COMPOUNDS_FILE, "r", encoding="utf-8") as f:
    compounds = json.load(f)

print(f"Found {len(compounds)} compounds\n")

# Create audio directory (no subdirectories)
audio_dir = Path(__file__).parent.parent / "data" / "audio"
audio_dir.mkdir(parents=True, exist_ok=True)

# Process all compounds
for data in compounds:
    doc_id = data["doc_id"]
    iupac_name = data["iupac_name"]

    # Simple path: all audio files in single directory
    audio_path = audio_dir / f"{doc_id}.wav"

    # Skip if already exists
    if audio_path.exists():
        print(f"⏭️  Skipping {doc_id} (already exists)")
        continue

    # Generate TTS using Gemini
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=iupac_name,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name='Kore',
                    )
                )
            ),
        )
    )

    # Extract and save audio
    audio_data = response.candidates[0].content.parts[0].inline_data.data
    wave_file(str(audio_path), audio_data)

    print(f"Generated: {audio_path}")

    # Rate limit: 3 requests per minute (20 seconds between requests)
    time.sleep(20)

print("Done!")
