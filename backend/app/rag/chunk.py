"""Section-aware chunking. Chunks never cross a section boundary; long sections are split on
sentence/paragraph boundaries with a small overlap. Each chunk keeps page + section."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.extract import Block
from app.rag.normalize import detect_language

_SENT = re.compile(r"(?<=[\.\!\?؟。])\s+|\n+")


@dataclass
class Chunk:
    index: int
    page: int | None
    section: str
    text: str
    language: str


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s.strip()]


def _join(sentences: list[str], section: str) -> str:
    if sentences and section and sentences[0] == section:
        return (sentences[0] + "\n" + " ".join(sentences[1:])).strip()
    return " ".join(sentences).strip()


def chunk_blocks(blocks: list[Block], max_chars: int = 900, overlap_chars: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for b in blocks:
        sentences = split_sentences(b.text)
        cur: list[str] = []
        size = 0
        for s in sentences:
            if size + len(s) > max_chars and cur:
                text = _join(cur, b.section)
                chunks.append(Chunk(len(chunks), b.page, b.section, text, detect_language(text)))
                tail: list[str] = []
                tsize = 0
                for prev in reversed(cur):
                    if tsize + len(prev) > overlap_chars:
                        break
                    tail.insert(0, prev)
                    tsize += len(prev)
                cur, size = tail, tsize
            cur.append(s)
            size += len(s) + 1
        if cur:
            text = _join(cur, b.section)
            if len(text) >= 20 or not chunks or text.strip() != (b.section or "").strip():
                chunks.append(Chunk(len(chunks), b.page, b.section, text, detect_language(text)))
    return chunks
