import hashlib
from pathlib import Path


def chunk_document(source: str, text: str, *, size: int = 900, overlap: int = 120) -> list[dict]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require 0 <= overlap < size")
    text = text.strip()
    chunks = []
    for start in range(0, len(text), size - overlap):
        content = text[start : start + size]
        if not content.strip():
            continue
        chunk_id = hashlib.sha256(f"{source}:{start}:{content}".encode()).hexdigest()[:32]
        chunks.append({"id": chunk_id, "source": source, "content": content})
        if start + size >= len(text):
            break
    return chunks


def read_knowledge(directory: Path) -> list[dict]:
    chunks = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(chunk_document(path.name, path.read_text()))
    return chunks
