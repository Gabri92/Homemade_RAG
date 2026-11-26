from homerag.ingest import (
    attach_intro_to_untitled_tables,
    clean,
    merge_continued_tables,
    remove_pull_quotes,
    remove_repeated_headings,
    title_from_spanning_row,
)
from homerag.models import Block

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


def test_merged_blocks_keep_the_page_where_they_start() -> None:
    intro = Block("paragraph", "Scoring:", CH1, page="41")
    untitled = Block("table", UNTITLED, CH1, page="42")
    week1 = Block("table", WEEK1, CH1, page="120")
    week2 = Block("table", WEEK2, CH1, page="121")

    assert attach_intro_to_untitled_tables([intro, untitled])[0].page == "41"
    assert merge_continued_tables([week1, week2])[0].page == "120"


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


# --- #4 remove_pull_quotes -------------------------------------------------------

# Synthetic text: never sentences from the real book.
ORIGINAL = (
    "Sleep is the quiet half of every plan. Your own logbook will show how much travel "
    "and work stress you can absorb, but a short night before a key day is a good reason "
    "to swap the hard session for an easy spin and move it to the weekend."
)
PULL_QUOTE = (
    "A short night before a key day is a good reason to swap the hard session for an easy spin."
)


def test_pull_quote_before_its_original_is_removed() -> None:
    blocks = [para("Intro."), para(PULL_QUOTE), para("Other text."), para(ORIGINAL)]

    assert remove_pull_quotes(blocks) == [para("Intro."), para("Other text."), para(ORIGINAL)]


def test_pull_quote_after_its_original_is_removed() -> None:
    assert remove_pull_quotes([para(ORIGINAL), para(PULL_QUOTE)]) == [para(ORIGINAL)]


def test_pull_quote_of_another_file_is_kept() -> None:
    blocks = [para(ORIGINAL, CH1), para(PULL_QUOTE, CH2)]

    assert remove_pull_quotes(blocks) == blocks


def test_similar_paragraphs_of_similar_length_are_both_kept() -> None:
    # e.g. two workout variants that differ only in a few details
    variant = ORIGINAL.replace("hard session", "long ride")

    assert remove_pull_quotes([para(ORIGINAL), para(variant)]) == [para(ORIGINAL), para(variant)]


def test_short_label_referenced_by_a_paragraph_is_kept() -> None:
    label = "SIDEBAR 1.1 Rating Your Sleep Habits"
    text = f"How well do you sleep? {label}, at the end of this chapter, will help you decide."

    assert remove_pull_quotes([para(label), para(text)]) == [para(label), para(text)]


def test_unrelated_short_sentence_is_kept() -> None:
    blocks = [para("Rest is part of training."), para(ORIGINAL)]

    assert remove_pull_quotes(blocks) == blocks


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
        para(PULL_QUOTE),
        para(ORIGINAL),
        table(WEEK1),
        table(WEEK2),
        para("How to determine rating:"),
        table(UNTITLED),
    ]

    once = clean(blocks)

    assert clean(once) == once


def heading(text: str, source: str = CH1, level: int = 1) -> Block:
    return Block("heading", text, source, level=level)


def test_heading_repeated_right_after_itself_is_dropped() -> None:
    blocks = [heading("Recovery Basics"), heading("recovery basics"), para("Sleep matters.")]

    assert remove_repeated_headings(blocks) == [heading("Recovery Basics"), para("Sleep matters.")]


def test_same_heading_in_another_file_or_after_text_is_kept() -> None:
    blocks = [
        heading("Summary"),
        heading("Summary", source=CH2),
        para("Text."),
        heading("Summary", source=CH2),
    ]

    assert remove_repeated_headings(blocks) == blocks


SPANNING = (
    "| Recovery Methods | Recovery Methods |\n| --- | --- |\n| Method | Time |\n| Sleep | 8 h |"
)


def test_spanning_first_row_of_an_untitled_table_becomes_its_title() -> None:
    assert title_from_spanning_row([table(SPANNING)]) == [
        table("Recovery Methods\n| Method | Time |\n| --- | --- |\n| Sleep | 8 h |")
    ]


def test_table_already_titled_by_its_intro_keeps_its_rows() -> None:
    titled = table(f"Accidents in the tunnel:\n{SPANNING}")

    assert title_from_spanning_row([titled]) == [titled]


def test_spanning_row_runs_after_the_intro_is_attached() -> None:
    blocks = [para("Accidents in the tunnel:"), table(SPANNING)]

    assert clean(blocks) == [table(f"Accidents in the tunnel:\n{SPANNING}")]
