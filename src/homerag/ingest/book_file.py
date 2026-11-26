"""book.json: the versioned hand-off file between ingestion and the rest of the pipeline."""

import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any  # book.json data: values of mixed types, checked when read

from homerag.models import Block, Book, Section

# Bump whenever the shape of Book/Section/Block changes: old files must be regenerated.
SCHEMA_VERSION = 2


def save_book(book: Book, path: Path) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "homerag_version": version("homerag"),
        "source": book.source,
        "sections": [asdict(section) for section in book.sections],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def load_book(path: Path) -> Book:
    payload = json.loads(path.read_text(encoding="utf-8"))
    found = payload.get("schema_version")
    if found != SCHEMA_VERSION:
        raise ValueError(
            f"{path}: schema_version {found}, expected {SCHEMA_VERSION}. "
            "Regenerate it with `homerag ingest`."
        )
    sections = tuple(_section(data) for data in payload["sections"])
    return Book(source=payload["source"], sections=sections)


def _section(data: dict[str, Any]) -> Section:
    # JSON has lists where the dataclasses have tuples.
    return Section(
        **{
            **data,
            "path": tuple(data["path"]),
            "blocks": tuple(Block(**block) for block in data["blocks"]),
        }
    )
