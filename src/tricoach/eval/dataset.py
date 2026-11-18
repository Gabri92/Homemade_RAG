"""Golden dataset: hand-written questions, reference answers and the book sections behind them.

`eval/datasets/golden.jsonl` holds one JSON object per line. Each line is validated with
`GoldenQuestion` (field types plus per-category rules); `load_golden` adds the checks that
need the whole file (unique ids, follow-ups pointing at an earlier question).
"""

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from tricoach.models import Book

Category = Literal[
    "factual", "table", "conceptual", "multi_hop", "out_of_scope", "follow_up", "non_english"
]

ENGLISH = "en"
# Categories whose answer is not in the book: the expected output is a refusal or the
# language-gate notice, so there is no section to cite.
_NO_SECTIONS: frozenset[Category] = frozenset({"out_of_scope", "non_english"})
_MIN_SECTIONS: dict[Category, int] = {"multi_hop": 2}


class GoldenQuestion(BaseModel):
    """One golden-set question.

    `language` is the expected outcome of the language gate: `en` passes, any other
    ISO 639-1 code is blocked. `reference_answer` is a hand-written paraphrase, never a
    quote from the book (the file is committed). `relevant_section_ids` are `Section.id`
    values from `book.json`. `previous_id` links a follow-up to the earlier question.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    id: str = Field(pattern=r"^q-\d{3,}$")
    question: str = Field(min_length=1)
    category: Category
    reference_answer: str | None = Field(default=None, min_length=1)
    relevant_section_ids: tuple[str, ...] = ()
    previous_id: str | None = None
    language: str = Field(default=ENGLISH, pattern=r"^[a-z]{2}$")

    @model_validator(mode="after")
    def _check_category_rules(self) -> Self:
        problems = [*_language_problems(self), *_section_problems(self), *_follow_up_problems(self)]
        if problems:
            raise ValueError("; ".join(problems))
        return self


def _language_problems(question: GoldenQuestion) -> list[str]:
    # Only non_english messages are blocked by the gate: they have no answer to compare.
    blocked = question.category == "non_english"
    problems = []
    if blocked and question.language == ENGLISH:
        problems.append("non_english needs a language other than 'en'")
    if not blocked and question.language != ENGLISH:
        problems.append(f"{question.category} needs language 'en'")
    if blocked and question.reference_answer is not None:
        problems.append("non_english takes no reference_answer (the gate notice is fixed)")
    if not blocked and question.reference_answer is None:
        problems.append(f"{question.category} needs a reference_answer")
    return problems


def _section_problems(question: GoldenQuestion) -> list[str]:
    count = len(question.relevant_section_ids)
    if question.category in _NO_SECTIONS:
        return [f"{question.category} cites no sections, got {count}"] if count else []
    minimum = _MIN_SECTIONS.get(question.category, 1)
    if count < minimum:
        return [f"{question.category} needs at least {minimum} section(s), got {count}"]
    return []


def _follow_up_problems(question: GoldenQuestion) -> list[str]:
    if (question.category == "follow_up") == (question.previous_id is not None):
        return []
    return ["previous_id is required for follow_up and allowed only there"]


def load_golden(path: Path) -> list[GoldenQuestion]:
    """Load and validate a golden-set JSONL file; blank lines are skipped.

    Raises ValueError with the file and line number of the first invalid line, or with
    every dataset-level problem (duplicate ids, follow-ups not pointing backwards).
    """
    questions = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            questions.append(GoldenQuestion.model_validate_json(line))
        except ValidationError as error:
            raise ValueError(f"{path}:{number}: {error}") from error
    problems = _dataset_problems(questions)
    if problems:
        raise ValueError(f"{path}:\n" + "\n".join(problems))
    return questions


def _dataset_problems(questions: list[GoldenQuestion]) -> list[str]:
    problems = []
    seen: set[str] = set()
    for question in questions:
        if question.id in seen:
            problems.append(f"{question.id}: duplicate id")
        if question.previous_id is not None and question.previous_id not in seen:
            problems.append(
                f"{question.id}: previous_id {question.previous_id!r} is not an earlier question"
            )
        seen.add(question.id)
    return problems


def check_references(questions: list[GoldenQuestion], book: Book) -> list[str]:
    """List the cited section ids that are missing from `book` or excluded from the index.

    Section ids are stable across runs, but an ingestion fix can still rename or drop a
    section: this check keeps that from silently orphaning golden-set references.
    """
    included = {section.id: section.include for section in book.sections}
    problems = []
    for question in questions:
        for section_id in question.relevant_section_ids:
            if section_id not in included:
                problems.append(f"{question.id}: unknown section {section_id!r}")
            elif not included[section_id]:
                problems.append(f"{question.id}: section {section_id!r} is excluded from the index")
    return problems
