from tricoach.ingest import attach_intro_to_untitled_tables, clean, merge_continued_tables
from tricoach.models import Block

CH1, CH2 = "ch01.xhtml", "ch02.xhtml"


def para(text: str, source: str = CH1) -> Block:
    return Block("paragraph", text, source)


def table(text: str, source: str = CH1) -> Block:
    return Block("table", text, source)


WEEK1 = "TABLE 9.3 Plan\n| WEEK 1 | MON |\n| --- | --- |\n| Swim | Low |"
WEEK2 = "| WEEK 2 | MON |\n| --- | --- |\n| Swim | High |"
WEEK3 = "| WEEK 3 | MON |\n| --- | --- |\n| Bike | Low |"
UNTITLED = "| SCORE | RATING |\n| --- | --- |\n| 10 | Good |"


# --- #8 merge_continued_tables ---------------------------------------------------


def test_untitled_tables_right_after_a_table_are_merged_into_it() -> None:
    blocks = [para("Intro."), table(WEEK1), table(WEEK2), table(WEEK3), para("After.")]

    assert merge_continued_tables(blocks) == [
        para("Intro."),
        table(f"{WEEK1}\n\n{WEEK2}\n\n{WEEK3}"),
        para("After."),
    ]


def test_titled_table_after_a_table_is_not_merged() -> None:
    other = "TABLE 9.4 Other\n| A |\n| --- |"
    blocks = [table(WEEK1), table(other)]

    assert merge_continued_tables(blocks) == blocks


def test_tables_separated_by_another_block_are_not_merged() -> None:
    blocks = [table(WEEK1), para("Text in between."), table(WEEK2)]

    assert merge_continued_tables(blocks) == blocks


def test_tables_in_different_files_are_not_merged() -> None:
    blocks = [table(WEEK1, CH1), table(WEEK2, CH2)]

    assert merge_continued_tables(blocks) == blocks


# --- #9 attach_intro_to_untitled_tables ------------------------------------------


def test_paragraph_before_untitled_table_becomes_its_title() -> None:
    blocks = [para("How to determine rating:"), table(UNTITLED), para("After.")]

    assert attach_intro_to_untitled_tables(blocks) == [
        table(f"How to determine rating:\n{UNTITLED}"),
        para("After."),
    ]


def test_titled_table_keeps_its_preceding_paragraph() -> None:
    blocks = [para("Text."), table(WEEK1)]

    assert attach_intro_to_untitled_tables(blocks) == blocks


def test_untitled_table_after_a_heading_or_list_is_left_alone() -> None:
    heading = Block("heading", "Scoring", CH1, level=3)
    item = Block("list_item", "One item", CH1)

    for previous in (heading, item):
        assert attach_intro_to_untitled_tables([previous, table(UNTITLED)]) == [
            previous,
            table(UNTITLED),
        ]


def test_paragraph_from_another_file_is_not_attached() -> None:
    blocks = [para("End of chapter one.", CH1), table(UNTITLED, CH2)]

    assert attach_intro_to_untitled_tables(blocks) == blocks


# --- clean: order and idempotence ------------------------------------------------


def test_split_untitled_table_is_merged_and_titled_by_its_intro() -> None:
    part_two = "| 11 | Fair |"
    blocks = [para("Scoring:"), table(UNTITLED), table(part_two), para("After.")]

    assert clean(blocks) == [
        table(f"Scoring:\n{UNTITLED}\n\n{part_two}"),
        para("After."),
    ]


def test_clean_is_idempotent() -> None:
    blocks = [
        para("Intro."),
        table(WEEK1),
        table(WEEK2),
        para("How to determine rating:"),
        table(UNTITLED),
    ]

    once = clean(blocks)

    assert clean(once) == once
