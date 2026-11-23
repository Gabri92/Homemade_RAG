# Command cheat sheet

Commands available now, grouped by task. The full list, including the ones planned for Phase 3 (`ask`, `eval run`, `eval compare`), is in `docs/steering/tech.md`. `uv run homerag --help` (or `<command> --help`) prints the live options.

Everything under `data/` is gitignored: outputs written there never reach the repository.

## Setup

| Command | What it does |
|---|---|
| `uv sync` | Install dependencies (never a direct `pip install`) |
| `uv run pre-commit install` | Enable the git hooks (once per clone) |

## Ingestion

| Command | What it does |
|---|---|
| `uv run homerag ingest data/raw/<book>.epub` | Load + clean + structure → `data/processed/book.json`. `--output <path>` to write elsewhere |
| `uv run homerag inspect data/raw/<book>.epub` | Quality report (numbers only, no book text). Exit code 1 on warnings |
| `uv run homerag dump data/raw/<book>.epub` | Raw loader blocks → `data/processed/blocks_raw.txt` |
| `uv run homerag dump data/raw/<book>.epub --clean` | Blocks after the Cleaner → `data/processed/blocks_clean.txt` |
| `git diff --no-index data/processed/blocks_raw.txt data/processed/blocks_clean.txt` | What the Cleaner changed |

## Index and search (Phase 3)

| Command | What it does |
|---|---|
| `uv run homerag index` | Chunk + embed the document of `configs/experiments/baseline.yaml` → `data/index/<document>/<strategy>-<hash>/` (`vectors.npy`, `chunks.json`, `meta.json`). Reuses the index when it is up to date; rebuilds it when `book.json` or the chunking/embedding settings changed. First run downloads bge-m3 (~2.2 GB) into the Hugging Face cache |
| `uv run homerag index --config configs/experiments/<name>.yaml` | Same, for another experiment. Experiments that change only retrieval, generation or judge settings share the same index |

| `uv run homerag search "How long is the base period?"` | Retrieval only, no LLM: rank, score, chunk id, section path, page of the top-k chunks. Needs the index (`homerag index`) |
| `uv run homerag search "..." --text` | Same, plus a short snippet of each chunk, for your own terminal only (never paste it into issues, posts or logs) |

Embeddings are cached in `data/cache/embeddings/` (one `.npy` per model + text): deleting the folder only costs recomputation.

## Golden set

| Command | What it does |
|---|---|
| `uv run homerag sections` | List section ids, page ranges and `[EXCLUDED]` flags (no book text) → `data/processed/sections.txt`: the ids to cite. `--book` / `--output` for other paths. Re-run after every `ingest`; cite only sections without `[EXCLUDED]` |
| `uv run homerag eval check` | Validate `eval/datasets/golden.jsonl` and check that every cited section exists in `data/processed/book.json` and is indexed. Exit code 1 on any problem |
| `uv run homerag eval check <file.jsonl> --book <book.json>` | Same, on another file or book |
| `uv run homerag eval check eval/datasets/example.jsonl` | Try the format on the synthetic example (its section ids are made up, so they are reported) |

Typical loop while writing questions:
1. `uv run homerag ingest data/raw/<book>.epub` (only if `book.json` is missing or ingestion changed);
2. `uv run homerag sections`, then find the section in `data/processed/sections.txt` and copy its id;
3. write the line in `golden.jsonl` (format: `docs/architecture.md` §7.1);
4. `uv run homerag eval check`;
5. `golden.jsonl` is gitignored (ADR 0004): keep a backup of your own. Every commit that touches code still re-runs the check against the current ingestion.

## Quality (definition of done)

| Command | What it does |
|---|---|
| `uv run ruff check . --fix` | Lint, with automatic fixes |
| `uv run ruff format .` | Format |
| `uv run mypy src` | Type check (`--strict`) |
| `uv run pytest` | All tests: unit + real book + corpus (book/corpus skipped when the files are missing) |
| `uv run pytest tests/unit` | Unit tests only: the fast loop (< 1 s) |
| `uv run pytest -m book` | Real-book checks only, including the golden-set references |
| `uv run pytest -m corpus` | Generalization on the ePubs in `data/corpus/` |
| `uv run pre-commit run --all-files` | Run every git hook without committing |

All green before calling something done:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

## Branches and pull requests

Every change reaches `main` through a pull request (rules: `docs/steering/conventions.md`, "Git").

| Command | What it does |
|---|---|
| `git switch main && git pull` | Start from an up-to-date `main` |
| `git switch -c <type>/<name>` | New branch: `feat/phase-3-…`, `exp/<name>`, `fix/…`, `docs/…`, `chore/…` |
| `git push -u origin <type>/<name>` | Publish the branch; the output prints the link to open the pull request |
| `git switch main && git pull && git branch -d <type>/<name>` | After the merge on GitHub: update `main` and delete the local branch |
| `git tag -a vX.Y.Z -m "…" && git push origin vX.Y.Z` | Phase release: annotated tag on the merge commit in `main` |
