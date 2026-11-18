"""Human-readable dump of blocks, for inspecting what the pipeline sees."""

from tricoach.models import Block


def format_blocks(blocks: list[Block]) -> str:
    """One entry per block, tagged with kind, level, source, page and role."""
    return "\n".join(_format_block(block) for block in blocks) + "\n"


def _format_block(block: Block) -> str:
    tag = block.kind if block.level is None else f"{block.kind} L{block.level}"
    where = [block.source, *([f"p. {block.page}"] if block.page else []), block.role]
    # Multi-line blocks (tables) are indented so each entry stays visually separate.
    text = block.text.replace("\n", "\n    ")
    return f"[{tag}] {' · '.join(where)}\n    {text}"
