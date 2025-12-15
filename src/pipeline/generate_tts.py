"""Generate TTS audio files for chemistry compounds using Piper (local/offline).

Usage:
    uv run src/pipeline/generate_tts.py [--force]

Requirements:
    1. Download Piper: https://github.com/rhasspy/piper/releases
    2. Download voice model (en_US-lessac-medium recommended)
    3. Set PIPER_BIN and PIPER_MODEL in .env

This reads chemistry_data.json, generates audio for items without audio files.
Run upload_to_s3.py after to sync to S3.
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
JSON_FILE = DATA_DIR / "chemistry_data.json"

# Audio output directories
COMPOUNDS_AUDIO = DATA_DIR / "compounds" / "audio"
ELEMENTS_AUDIO = DATA_DIR / "elements" / "audio"

# Piper configuration
PIPER_BIN = os.getenv("PIPER_BIN", "/usr/local/bin/piper")
PIPER_MODEL = os.getenv("PIPER_MODEL", str(PROJECT_ROOT / "models" / "en_US-lessac-medium.onnx"))


def generate_audio(text: str, output_path: Path) -> bool:
    """Generate TTS audio using Piper."""
    cmd = [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", str(output_path)]

    result = subprocess.run(
        cmd,
        input=text,
        capture_output=True,
        text=True,
        timeout=10,
    )

    return result.returncode == 0 and output_path.exists()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate all audio")
    args = parser.parse_args()

    # Verify Piper
    if not Path(PIPER_BIN).exists():
        print(f"Error: Piper not found at {PIPER_BIN}")
        print("Download from: https://github.com/rhasspy/piper/releases")
        return 1

    if not Path(PIPER_MODEL).exists():
        print(f"Error: Piper model not found at {PIPER_MODEL}")
        print("Download en_US-lessac-medium.onnx from Piper releases")
        return 1

    # Create directories
    COMPOUNDS_AUDIO.mkdir(parents=True, exist_ok=True)
    ELEMENTS_AUDIO.mkdir(parents=True, exist_ok=True)

    # Load data
    print(f"Loading {JSON_FILE}...")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Found {len(data)} items")
    print(f"Piper: {PIPER_BIN}")
    print(f"Model: {PIPER_MODEL}\n")

    generated = 0
    skipped = 0
    failed = 0

    for idx, item in enumerate(data, 1):
        doc_id = item["doc_id"]
        item_type = item["type"]
        name = item["iupac_name"]

        # Determine output path
        if item_type == "element":
            audio_path = ELEMENTS_AUDIO / f"{doc_id}.wav"
        else:
            audio_path = COMPOUNDS_AUDIO / f"{doc_id}.wav"

        # Skip if exists (unless --force)
        if audio_path.exists() and not args.force:
            print(f"[{idx}/{len(data)}] ⏭️  {name} (exists)")
            skipped += 1
            continue

        # Generate TTS
        try:
            print(f"[{idx}/{len(data)}] 🎤 {name}...", end=" ", flush=True)

            if generate_audio(name, audio_path):
                size_kb = audio_path.stat().st_size / 1024
                print(f"✓ ({size_kb:.1f} KB)")
                generated += 1
            else:
                print("❌ Failed")
                failed += 1

        except subprocess.TimeoutExpired:
            print("❌ Timeout")
            failed += 1
        except Exception as e:
            print(f"❌ {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Generated: {generated}, Skipped: {skipped}, Failed: {failed}")
    print(f"\nAudio files in:")
    print(f"  - {COMPOUNDS_AUDIO}")
    print(f"  - {ELEMENTS_AUDIO}")
    print(f"\nNext: Run upload_to_s3.py to sync to S3")

    return 0


if __name__ == "__main__":
    exit(main())
