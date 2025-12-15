"""Upload chemistry chatbot assets to S3 and update JSON paths.

Usage:
    uv run src/pipeline/upload_to_s3.py --bucket chemistry-chatbot-assets
"""

import argparse
import json
import mimetypes
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
JSON_FILE = DATA_DIR / "chemistry_data.json"
REGION = "ap-southeast-1"


def upload_directory(s3_client, bucket: str, local_dir: Path) -> dict:
    """Upload directory to S3, return path mappings."""
    uploaded = {}

    if not local_dir.exists():
        print(f"  ⚠ Not found: {local_dir}")
        return uploaded

    for file_path in local_dir.rglob("*"):
        if file_path.is_file():
            relative = file_path.relative_to(DATA_DIR)
            s3_key = str(relative).replace("\\", "/")

            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = "audio/wav" if file_path.suffix == ".wav" else "image/png"

            s3_client.upload_file(
                str(file_path), bucket, s3_key,
                ExtraArgs={"ContentType": content_type}
            )
            s3_url = f"https://{bucket}.s3.{REGION}.amazonaws.com/{s3_key}"
            uploaded[str(relative)] = s3_url
            print(f"  ✓ {relative}")

    return uploaded


def update_json(path_mapping: dict) -> int:
    """Update chemistry_data.json with S3 URLs."""
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for compound in data:
        for key in ["image_path", "audio_path"]:
            if compound.get(key):
                normalized = compound[key].replace("\\", "/")
                if normalized in path_mapping:
                    compound[key] = path_mapping[normalized]
                    count += 1

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", default="chemistry-chatbot-assets")
    args = parser.parse_args()

    print(f"\nUploading to s3://{args.bucket} ({REGION})\n")

    s3 = boto3.client("s3", region_name=REGION)
    mappings = {}

    for subdir in ["compounds", "elements", "isomers"]:
        print(f"[{subdir}]")
        mappings.update(upload_directory(s3, args.bucket, DATA_DIR / subdir))

    print(f"\n✓ Uploaded {len(mappings)} files")

    updated = update_json(mappings)
    print(f"✓ Updated {updated} paths in chemistry_data.json")

    print(f"\nBase URL: https://{args.bucket}.s3.{REGION}.amazonaws.com/")


if __name__ == "__main__":
    main()
