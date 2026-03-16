"""Utility script to regenerate agent/knowledge_base.md from notebook markdown cells.

Run from the project root:
    uv run python agent/build_knowledge_base.py

This overwrites agent/knowledge_base.md with freshly extracted content.
The generated file should be reviewed and committed — it is the sole textual
source of truth for the ETF Portfolio Agent.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
OUTPUT_FILE = Path(__file__).parent / "knowledge_base.md"

NOTEBOOK_ORDER = [
    "01_data_collection.ipynb",
    "02_etf_screening.ipynb",
    "03_portfolio_construction.ipynb",
    "04_performance_tracking.ipynb",
]

NOTEBOOK_TITLES = {
    "01_data_collection.ipynb": "Notebook 01 — Data Collection",
    "02_etf_screening.ipynb": "Notebook 02 — ETF Screening",
    "03_portfolio_construction.ipynb": "Notebook 03 — Portfolio Construction",
    "04_performance_tracking.ipynb": "Notebook 04 — Performance Tracking",
}


def extract_markdown_cells(notebook_path: Path) -> list[str]:
    """Return all markdown cell sources from a .ipynb file."""
    with open(notebook_path) as f:
        nb = json.load(f)
    cells = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "markdown":
            source = "".join(cell.get("source", []))
            if source.strip():
                cells.append(source.strip())
    return cells


def build_knowledge_base() -> None:
    sections = [
        "# ETF ISA Portfolio — Knowledge Base\n\n"
        "*Auto-generated from notebooks 01–04. "
        "Run `uv run python agent/build_knowledge_base.py` to regenerate.*\n"
    ]

    for notebook_name in NOTEBOOK_ORDER:
        path = NOTEBOOKS_DIR / notebook_name
        if not path.exists():
            print(f"WARNING: {path} not found — skipping", file=sys.stderr)
            continue

        title = NOTEBOOK_TITLES[notebook_name]
        cells = extract_markdown_cells(path)
        if not cells:
            print(f"WARNING: No markdown cells found in {notebook_name}", file=sys.stderr)
            continue

        sections.append(f"\n---\n\n## {title}\n")
        for cell in cells:
            sections.append(f"\n{cell}\n")

        print(f"Extracted {len(cells)} markdown cells from {notebook_name}")

    content = "\n".join(sections)
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"\nWrote {len(content)} characters to {OUTPUT_FILE}")


if __name__ == "__main__":
    build_knowledge_base()
