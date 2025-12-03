"""Generate TTS audio files for all elements and compounds using Piper (local, offline)"""

import json
import subprocess
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent.parent  # Project root
DATA_FILE = BASE_DIR / "data" / "chemistry_data.json"
AUDIO_DIR = BASE_DIR / "data" / "audio"
PIPER_BIN = "/tmp/piper/piper"
PIPER_MODEL = BASE_DIR / "models" / "tts" / "en_US-lessac-medium.onnx"

# Verify Piper binary exists
if not Path(PIPER_BIN).exists():
    raise FileNotFoundError(f"Piper binary not found at {PIPER_BIN}")

# Verify model exists
if not PIPER_MODEL.exists():
    raise FileNotFoundError(f"Piper model not found at {PIPER_MODEL}")

# Load all data
print(f"Loading chemistry data from {DATA_FILE}...")
with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

elements = [x for x in data if x['type'] == 'element']
compounds = [x for x in data if x['type'] == 'compound']

print(f"Found {len(data)} items ({len(elements)} elements, {len(compounds)} compounds)\n")

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

    # Get pronunciation text (all items have iupac_name now)
    text_to_speak = item["iupac_name"]

    if item_type == "element":
        audio_path = AUDIO_DIR / "elements" / f"{doc_id}.wav"
    else:  # compound
        audio_path = AUDIO_DIR / f"{doc_id}.wav"

    # Skip if already exists
    if audio_path.exists():
        file_size = audio_path.stat().st_size / 1024
        print(f"[{idx}/{total}] ⏭️  Skipping {text_to_speak} (exists, {file_size:.1f} KB)")
        skipped += 1
        continue

    # Generate TTS using Piper
    try:
        print(f"[{idx}/{total}] 🎤 Generating: {text_to_speak} ({item_type})...", end=" ", flush=True)

        # Run Piper command
        cmd = [
            PIPER_BIN,
            "--model", str(PIPER_MODEL),
            "--output_file", str(audio_path)
        ]

        result = subprocess.run(
            cmd,
            input=text_to_speak,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and audio_path.exists():
            file_size = audio_path.stat().st_size / 1024  # KB
            print(f"✓ ({file_size:.1f} KB)")
            generated += 1
        else:
            print(f"❌ Failed (return code: {result.returncode})")
            if result.stderr:
                print(f"    Error: {result.stderr[:100]}")
            failed += 1

    except subprocess.TimeoutExpired:
        print(f"❌ Timeout")
        failed += 1
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        failed += 1

# Summary
print(f"\n{'='*60}")
print(f"TTS Generation Summary:")
print(f"  ✓ Generated: {generated}/{total}")
print(f"  ⏭️  Skipped (existing): {skipped}/{total}")
print(f"  ❌ Failed: {failed}/{total}")
print(f"\nAudio files saved to:")
print(f"  - Elements: {AUDIO_DIR / 'elements'}/*.wav")
print(f"  - Compounds: {AUDIO_DIR}/*.wav")
print(f"\nFormat: WAV (22050 Hz, 16-bit, mono)")
print(f"Model: Piper en_US-lessac-medium (local, offline)")
if generated > 0:
    print(f"Total time: Fast! (~{generated * 0.15:.1f} seconds)")
print("\nDone!")
