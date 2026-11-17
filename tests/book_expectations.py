"""Expected facts about the real book, set once by inspection (see docs/ingestion-findings.md).

Only counts and short titles: never copy book text here.
"""

from pathlib import Path

BOOK_PATH = Path(__file__).parents[1] / "data" / "raw" / "The_Triathletes_Training_Bible.epub"

# Tables (finding #1 and #2)
TABLES = 37
TABLES_WITH_TITLE = 29
TABLE_11_1_TITLE = "TABLE 11.1 Common Morning Warning Indicators of Stress"
TABLE_9_2_PERIODS = {"Base 1", "Base 2", "Base 3", "Build 1", "Build 2"}

# Figures (finding #3)
FIGURES = 64
FIGURES_CAPTIONED_FIGURE = 39
TABLES_PUBLISHED_AS_IMAGES = 5
