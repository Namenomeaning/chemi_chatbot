"""Build deterministic chunks. Use --remote to embed and upload them to Cloudflare."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from app.services.chunking import read_knowledge  # noqa: E402


def cloudflare_token():
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if token:
        return token
    result = subprocess.run(
        [str(ROOT / "node_modules/.bin/wrangler"), "auth", "token", "--json"],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    return json.loads(result.stdout)["token"]


def sql_for(chunks):
    def quote(value):
        return "'" + value.replace("'", "''") + "'"

    rows = ["DELETE FROM knowledge_fts;"]
    for chunk in chunks:
        rows.append(
            "INSERT INTO knowledge_fts(id,source,content) VALUES("
            + ",".join(quote(chunk[key]) for key in ("id", "source", "content"))
            + ");"
        )
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--account-id", default=os.environ.get("CLOUDFLARE_ACCOUNT_ID"))
    parser.add_argument("--database-id", default="463019bc-8dba-4c51-95bc-d9abedaf7937")
    parser.add_argument("--index", default="chemi-knowledge")
    args = parser.parse_args()
    chunks = read_knowledge(ROOT / "knowledge")
    output = ROOT / ".knowledge-build"
    output.mkdir(exist_ok=True)
    (output / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2))
    (output / "knowledge.sql").write_text(sql_for(chunks))
    print(f"Built {len(chunks)} chunks from local Markdown.")
    if not args.remote:
        return
    if not args.account_id:
        parser.error("Set CLOUDFLARE_ACCOUNT_ID or --account-id")
    base = f"https://api.cloudflare.com/client/v4/accounts/{args.account_id}"
    # This token stays in process memory. Never print it or put it in command arguments.
    with httpx.Client(headers={"Authorization": f"Bearer {cloudflare_token()}"}, timeout=90) as client:

        def api(path, **kwargs):
            response = client.post(base + path, **kwargs)
            response.raise_for_status()
            body = response.json()
            if not body.get("success"):
                codes = [e.get("code") for e in body.get("errors", [])]
                raise RuntimeError(f"Cloudflare rejected {path}: codes={codes}")
            return body.get("result")

        api(f"/d1/database/{args.database_id}/query", json={"sql": (ROOT / "schema.sql").read_text()})
        for start in range(0, len(chunks), 20):
            batch = chunks[start : start + 20]
            embedding = api("/ai/run/@cf/baai/bge-base-en-v1.5", json={"text": [c["content"] for c in batch]})
            vectors = [
                {"id": chunk["id"], "values": values} for chunk, values in zip(batch, embedding["data"], strict=True)
            ]
            if any(len(v["values"]) != 768 for v in vectors):
                raise ValueError("Embedding dimension must be 768")
            payload = "\n".join(json.dumps(v) for v in vectors)
            api(
                f"/vectorize/v2/indexes/{args.index}/upsert",
                files={"vectors": ("vectors.ndjson", payload, "application/x-ndjson")},
            )
        # Update lexical data after all vectors have been submitted successfully.
        api(f"/d1/database/{args.database_id}/query", json={"sql": sql_for(chunks)})
    print(f"Uploaded {len(chunks)} vectors and lexical rows. Vectorize visibility is asynchronous.")


if __name__ == "__main__":
    main()
