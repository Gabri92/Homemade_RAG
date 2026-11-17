"""Human-readable dump of blocks, for inspecting what the pipeline sees."""

from tricoach.models import Block


def format_blocks(blocks: list[Block]) -> str:
    """One entry per block, tagged with kind, level and source."""
    return "\n".join(_format_block(block) for block in blocks) + "\n"


def _format_block(block: Block) -> str:
    tag = block.kind if block.level is None else f"{block.kind} L{block.level}"
    # Multi-line blocks (tables) are indented so each entry stays visually separate.
    text = block.text.replace("\n", "\n    ")
    return f"[{tag}] {block.source}\n    {text}"
