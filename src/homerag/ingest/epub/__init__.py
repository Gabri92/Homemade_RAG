"""ePub loader: ePub file -> list of format-independent blocks (one module per concern).

- `loader`: the container (spine, navigation, page carry-over between files);
- `html`: one document -> blocks; `tables`: tables -> Markdown;
- `roles`: what each file is (landmarks, epub:type);
- `pressbooks`: a tool's conventions, used only where EPUB semantics are missing.
"""

from homerag.ingest.epub.html import html_to_blocks
from homerag.ingest.epub.loader import epub_text, load_epub
from homerag.ingest.epub.roles import BODY, landmark_types, role_from_types

__all__ = [
    "BODY",
    "epub_text",
    "html_to_blocks",
    "landmark_types",
    "load_epub",
    "role_from_types",
]
