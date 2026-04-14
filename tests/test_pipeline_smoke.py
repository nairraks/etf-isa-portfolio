"""End-to-end pipeline smoke tests.

Executes each notebook in the book (01 → 04) top-to-bottom and asserts that
no cell raises. Catches regressions that unit tests miss — e.g. the
`KeyError: 'platform'` the notebook 02 equities cell used to raise when its
per-file `try/except` caught every CSV.

Opt-in: these tests are marked `@pytest.mark.pipeline` and skipped by the
default `pytest` run because they hit live data providers (AlphaVantage,
yfinance, InvestEngine API, JustETF scraper) and can take several minutes.

Invoke explicitly:
    uv run pytest -m pipeline                    # all four notebooks
    uv run pytest -m pipeline -k screening       # single notebook
    uv run pytest -m pipeline --pipeline-fast    # skip nb01 (JustETF scrape)
"""

from __future__ import annotations

from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

NOTEBOOK_DIR = Path(__file__).parent.parent / "notebooks"

# Ordered list — nb01 must run before nb02, etc. Test order matters if a
# downstream notebook reads artefacts a prior notebook writes.
NOTEBOOKS = [
    "01_data_collection.ipynb",
    "02_etf_screening.ipynb",
    "03_portfolio_construction.ipynb",
    "04_performance_tracking.ipynb",
]

# nb01 scrapes JustETF for every asset class — minutes of HTTP. Allow the
# caller to skip it when they just want to re-validate downstream plumbing.
HEAVY_NOTEBOOKS = {"01_data_collection.ipynb"}


@pytest.mark.pipeline
@pytest.mark.parametrize("notebook_name", NOTEBOOKS)
def test_notebook_runs_without_error(notebook_name, request):
    """Execute every cell of a notebook; fail on the first exception.

    On failure, pytest surfaces the cell index and traceback from nbclient,
    so a regression like `KeyError: 'platform'` points straight at the
    offending cell.
    """
    if request.config.getoption("--pipeline-fast") and notebook_name in HEAVY_NOTEBOOKS:
        pytest.skip(f"--pipeline-fast: skipping {notebook_name}")

    nb_path = NOTEBOOK_DIR / notebook_name
    assert nb_path.exists(), f"Notebook not found: {nb_path}"

    nb = nbformat.read(nb_path, as_version=4)

    # Run with the notebook's own cwd so relative paths (`data/raw/…`,
    # `../etf_utils`) resolve the same way they do in Jupyter.
    client = NotebookClient(
        nb,
        timeout=600,  # 10 min per cell ceiling — nb01 scraping can be slow
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOK_DIR)}},
        allow_errors=False,
    )

    try:
        client.execute()
    except CellExecutionError as exc:  # pragma: no cover — only on failure
        # Pinpoint the failing cell for quick diagnosis.
        failing_cell_idx = next(
            (i for i, c in enumerate(nb.cells)
             if c.cell_type == "code"
             and any(o.get("output_type") == "error" for o in c.get("outputs", []))),
            None,
        )
        pytest.fail(
            f"{notebook_name} failed at cell index {failing_cell_idx}:\n{exc}",
            pytrace=False,
        )
