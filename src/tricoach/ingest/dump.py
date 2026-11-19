"""Human-readable dumps of blocks and sections, for inspecting what the pipeline sees."""

from tricoach.models import Block, Book, Section


def format_blocks(blocks: list[Block]) -> str:
    """One entry per block, tagged with kind, level, source, page and role."""
    return "\n".join(_format_block(block) for block in blocks) + "\n"


def _format_block(block: Block) -> str:
    tag = block.kind if block.level is None else f"{block.kind} L{block.level}"
    where = [block.source, *([f"p. {block.page}"] if block.page else []), block.role]
    # Multi-line blocks (tables) are indented so each entry stays visually separate.
    text = block.text.replace("\n", "\n    ")
    return f"[{tag}] {' · '.join(where)}\n    {text}"


def format_sections(book: Book) -> str:
    """One line per section: id, page range, and a flag when it is not indexed. No body text.

    The ids are what the golden set cites (`relevant_section_ids`).
    """
    return "\n".join(_format_section(section) for section in book.sections) + "\n"


def _format_section(section: Section) -> str:
    first, last = section.first_page, section.last_page
    pages = "no page" if first is None else f"p. {first}" if first == last else f"p. {first}-{last}"
    excluded = "" if section.include else "  [EXCLUDED]"
    return f"{section.id}  {pages}{excluded}"
