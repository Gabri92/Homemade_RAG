"""Expected facts about the real book, set once by inspection (see docs/ingestion-findings.md).

Only counts and short titles: never copy book text here.
"""

from pathlib import Path

BOOK_PATH = Path(__file__).parents[2] / "data" / "raw" / "The_Triathletes_Training_Bible.epub"

# Tables (finding #1 and #2)
TABLES = 37
TABLES_WITH_TITLE = 29
TABLE_11_1_TITLE = "TABLE 11.1 Common Morning Warning Indicators of Stress"
TABLE_9_2_PERIODS = {"Base 1", "Base 2", "Base 3", "Build 1", "Build 2"}

# Split tables (finding #8): weekly plans published as one <table> per week
SPLIT_PLAN_TABLES = ("TABLE 9.3", "TABLE 9.4")
SPLIT_PLAN_WEEKS = ("| WEEK 1 |", "| WEEK 2 |", "| WEEK 3 |")
CONTINUATION_TABLES = 4

# Untitled tables (finding #9): questionnaire scoring tables, titled by their intro paragraph
UNTITLED_TABLES = 4

# Pull quotes (finding #4): measured against the HTML sidenotes (div.sidenote)
SIDENOTES = 214
PULL_QUOTES_REMOVED = 157

# Roles and pages (findings #5, #6, #10)
GLOSSARY_TERMS = 123
TABLE_11_1_PAGE = "172"  # verified by hand in the XHTML: marker page_172 opens the caption

# Structurer
CHAPTERS = 14
MORNING_WARNINGS_ID = "part-v-stress-rest-and-recovery/11-rest-and-recovery/morning-warnings"
EXCLUDED_ROLES = {
    "cover",
    "frontmatter",  # praise.xhtml (finding #11)
    "titlepage",
    "dedication",
    "acknowledgments",
    "backmatter",
    "bibliography",
    "index",
    "copyright-page",
}
AE1_RECOVERY_SECTIONS = 3  # same workout title for swim, bike and run

# Figures (finding #3)
FIGURES = 64
FIGURES_CAPTIONED_FIGURE = 39
TABLES_PUBLISHED_AS_IMAGES = 5
