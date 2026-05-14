
from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.state import FilingChunk

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 100


def chunk_filing_sections(
    chunks: list[FilingChunk],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[FilingChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    split_chunks: list[FilingChunk] = []
    for source_chunk in chunks:
        text_parts = splitter.split_text(source_chunk["text"])
        if not text_parts:
            continue

        for index, text_part in enumerate(text_parts, start=1):
            split_chunks.append(
                {
                    **source_chunk,
                    "chunk_id": f"{source_chunk['chunk_id']}:part-{index}",
                    "text": text_part,
                }
            )

    return split_chunks
