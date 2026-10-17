"""Check a deployed Worker. --full makes real model calls; --audio requires live R2."""

import argparse
import json
import os
import shlex
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def access_key():
    if value := os.environ.get("CHEMI_ACCESS_KEY"):
        return value
    path = ROOT / ".dev.vars"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("API_KEYS="):
                return shlex.split(line.split("=", 1)[1])[0].split(",")[0]
    raise SystemExit("Set CHEMI_ACCESS_KEY or API_KEYS in the local .dev.vars file")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://chemi.quangiz.me")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--audio", action="store_true")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=100) as client:
        for path in ("/health", "/ready"):
            response = client.get(path)
            response.raise_for_status()
            print(json.dumps({"check": path, "status": response.status_code}), flush=True)
        response = client.post("/query", json={"text": "hi"})
        assert response.status_code == 401, "Production must reject unauthenticated queries"
        client.headers["X-API-Key"] = access_key()

        def query(name, text, **fields):
            started = time.monotonic()
            response = client.post("/query", json={"text": text, **fields})
            response.raise_for_status()
            data = response.json()
            assert data["success"], name
            print(
                json.dumps(
                    {
                        "check": name,
                        "status": response.status_code,
                        "seconds": round(time.monotonic() - started, 2),
                        "citations": len(data.get("citations", [])),
                        "quiz": bool(data.get("quiz_data")),
                        "audio": bool(data.get("audio_base64")),
                    }
                ),
                flush=True,
            )
            return data

        query("greeting", "hi")
        if args.full:
            answer = query("grounded", "Ethanol là gì?")
            assert answer["citations"] and not answer["abstained"]
            followup = query("followup", "Công thức của nó là gì?", thread_id=answer["thread_id"])
            assert followup["citations"] and not followup["abstained"]
            assert query("abstention", "How to configure Kubernetes?")["abstained"]
            for kind, text in [
                ("mcq", "Tạo một câu hỏi trắc nghiệm về alcohol"),
                ("matching", "Tạo bài tập ghép cặp về alkane"),
                ("free_text", "Tạo bài tập tự luận về alcohol"),
                ("listening", "Tạo bài tập nghe listening về alcohol"),
            ]:
                quiz = query(kind, text)
                assert quiz.get("quiz_data") and quiz["quiz_data"]["type"] == kind
                if kind == "listening" and args.audio:
                    assert quiz.get("audio_base64"), "Listening requires audio from R2"
        if args.audio:
            assert query("speech", "Phát âm ethanol").get("audio_base64"), "Live R2 speech is missing"


if __name__ == "__main__":
    main()
