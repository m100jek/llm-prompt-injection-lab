import re
from pathlib import Path


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _chunk_document(text: str, source: str, min_chars: int = 50) -> list[dict]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks = []

    for paragraph in paragraphs:
        if len(paragraph) >= min_chars:
            chunks.append({"source": source, "text": paragraph})
            continue

        if chunks and chunks[-1]["source"] == source:
            merged = f"{chunks[-1]['text']}\n\n{paragraph}"
            chunks[-1] = {"source": source, "text": merged}
        else:
            chunks.append({"source": source, "text": paragraph})

    return [chunk for chunk in chunks if len(chunk["text"]) >= min_chars]


def _load_chunks(documents_dir: Path) -> list[dict]:
    chunks: list[dict] = []

    for path in sorted(documents_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        chunks.extend(_chunk_document(text, path.name))

    return chunks


def _score_chunk(query_tokens: set[str], chunk_tokens: set[str]) -> int:
    return len(query_tokens & chunk_tokens)


def retrieve(query: str, documents_dir: Path, top_k: int = 2) -> list[dict]:
    if not documents_dir.exists():
        return []

    chunks = _load_chunks(documents_dir)
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return chunks[:top_k]

    scored = []
    for chunk in chunks:
        score = _score_chunk(query_tokens, _tokenize(chunk["text"]))
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_scored = [chunk for score, chunk in scored if score > 0][:top_k]

    if top_scored:
        return top_scored

    return [chunk for _, chunk in scored[:top_k]]


def load_document(documents_dir: Path, filename: str) -> dict:
    path = documents_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    return {"source": filename, "text": path.read_text(encoding="utf-8")}
