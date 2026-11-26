"""The structure rules of docs/steering/structure.md, checked on the source code.

They read every module's imports (also those inside functions) with `ast`: no module is
imported, so these tests run in milliseconds and need no optional library.
"""

import ast
from pathlib import Path

import pytest

SRC = Path("src")
INTERFACES = "homerag.interfaces"

# Each external library and the only module (or package) allowed to import it.
OWNERS = {
    "anthropic": "homerag.llm",
    "torch": "homerag.embedding",
    "transformers": "homerag.embedding",
    "sentence_transformers": "homerag.embedding",
    "lingua": "homerag.language",
    "ebooklib": "homerag.ingest.epub",
    "bs4": "homerag.ingest.epub",
    "gradio": "homerag.interfaces.chat",
    "typer": "homerag.interfaces.cli",
}


def module_name(path: Path) -> str:
    parts = path.relative_to(SRC).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports_of(path: Path) -> set[str]:
    """Every module `path` imports, as written: "homerag.qa", "numpy", "numpy.typing"."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


MODULES = {module_name(path): imports_of(path) for path in sorted(SRC.rglob("*.py"))}


def within(module: str, owner: str) -> bool:
    return module == owner or module.startswith(owner + ".")


def test_the_source_tree_is_found() -> None:
    assert "homerag.qa" in MODULES
    assert "homerag.interfaces.cli" in MODULES


def test_the_core_never_imports_the_interfaces() -> None:
    offenders = {
        module: sorted(i for i in imports if within(i, INTERFACES))
        for module, imports in MODULES.items()
        if not within(module, INTERFACES)
    }

    assert {m: i for m, i in offenders.items() if i} == {}


@pytest.mark.parametrize(("library", "owner"), OWNERS.items())
def test_each_external_library_is_imported_by_its_module_only(library: str, owner: str) -> None:
    importers = {
        module for module, imports in MODULES.items() if any(within(i, library) for i in imports)
    }

    assert importers, f"{library}: no module imports it, is OWNERS out of date?"
    assert {m for m in importers if not within(m, owner)} == set()


def test_models_imports_no_other_project_module() -> None:
    assert {i for i in MODULES["homerag.models"] if within(i, "homerag")} == set()
