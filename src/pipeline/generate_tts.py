"""Generate TTS audio files for all elements and compounds using Gemini 2.5 Flash TTS."""

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
DATA_FILE = Path(__file__).parent.parent / "data" / "chemistry_data.json"
AUDIO_DIR = Path(__file__).parent.parent / "data" / "audio"

# Initialize Gemini client
api_key = os.getenv("GOOGLE_GEMINI_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_GEMINI_API_KEY not found in environment")
client = genai.Client(api_key=api_key)

# Helper function to save wave file
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

# Load all data
print(f"Loading chemistry data from {DATA_FILE}...")
with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Found {len(data)} items ({sum(1 for x in data if x['type']=='element')} elements, {sum(1 for x in data if x['type']=='compound')} compounds)\n")

# Create audio directories
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
(AUDIO_DIR / "elements").mkdir(exist_ok=True)

# Statistics
total = len(data)
generated = 0
skipped = 0
failed = 0

# Process all items
for idx, item in enumerate(data, 1):
    doc_id = item["doc_id"]
    item_type = item["type"]

    # Get pronunciation text
    if item_type == "element":
        # Elements: use iupac_name (English name)
        text_to_speak = item["iupac_name"]
        audio_filename = f"{doc_id}.wav"
        audio_path = AUDIO_DIR / "elements" / audio_filename
    else:  # compound
        # Compounds: use iupac_name
        text_to_speak = item.get("iupac_name", item["common_names"][0])
        audio_filename = f"{doc_id}.wav"
        audio_path = AUDIO_DIR / audio_filename

    # Skip if already exists
    if audio_path.exists():
        print(f"[{idx}/{total}] ⏭️  Skipping {text_to_speak} (already exists)")
        skipped += 1
        continue

    # Generate TTS using Gemini
    try:
        print(f"[{idx}/{total}] 🎤 Generating: {text_to_speak} ({item_type})...", end=" ", flush=True)

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text_to_speak,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Kore',  # Clear American English voice
                        )
                    )
                ),
            )
        )

        # Extract and save audio
        audio_data = response.candidates[0].content.parts[0].inline_data.data
        wave_file(str(audio_path), audio_data)

        file_size = audio_path.stat().st_size / 1024  # KB
        print(f"✓ ({file_size:.1f} KB)")
        generated += 1

        # Rate limit: 3 requests per minute (20 seconds between requests)
        # For safety, use 21 seconds
        if idx < total:  # Don't wait after last item
            time.sleep(21)

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        failed += 1
        # Wait a bit before retrying next item
        time.sleep(5)

# Summary
print(f"\n{'='*60}")
print(f"TTS Generation Summary:")
print(f"  ✓ Generated: {generated}/{total}")
print(f"  ⏭️  Skipped: {skipped}/{total}")
print(f"  ❌ Failed: {failed}/{total}")
print(f"\nAudio files saved to:")
print(f"  - Elements: {AUDIO_DIR / 'elements'}/*.wav")
print(f"  - Compounds: {AUDIO_DIR}/*.wav")
print(f"\nEstimated time: {generated * 21 / 60:.1f} minutes")
print("Done!")
