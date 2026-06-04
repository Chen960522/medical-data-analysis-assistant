"""Property-based tests for the data-preview row count.

Validates: Requirements 2.2
Property 4: 数据预览行数正确性 (Data preview row count correctness)

    For any dataset containing N rows (N >= 0), the data preview function SHALL
    return exactly ``min(10, N)`` rows.

Requirement 2.2:
    WHEN parsing is complete, THE Data_Parser SHALL display a data preview
    showing the first 10 rows.

Source of truth
---------------
The preview endpoint ``get_file_preview`` in ``app/api/v1/data.py`` computes
the preview as::

    result = parse_file(content, data_file.file_format)
    preview_rows = result.rows[:10]

So the preview is the first 10 rows of the parsed result. These tests exercise
that exact production path: they generate a CSV with ``N`` data rows, call the
real ``parse_file(csv_bytes, "csv")`` and apply the same ``result.rows[:10]``
slice the endpoint uses. The core invariant checked is that the preview returns
exactly ``min(10, N)`` rows and that they are the FIRST ``min(10, N)`` parsed
rows, in their original order.

Domain of valid inputs (documented restrictions, mirroring
``test_property_data_roundtrip.py``)
-------------------------------------------------------------------------------
  * A fixed small set of UNIQUE column names is used (``csv.DictReader``
    collapses duplicate header names). Column names are identifier-like.
  * Cell values are non-empty and free of ``,`` ``"`` ``\r`` ``\n`` so every
    row serializes to an unambiguous, non-blank CSV line. With >= 2 columns
    this also avoids the one ``csv`` edge case where a single-column row whose
    only value is empty would be written as a blank line and SKIPPED by
    ``DictReader`` (which would change the parsed row count).
"""

import csv
import io
import string

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_parser import parse_file

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

# The number of preview rows the endpoint exposes (``result.rows[:10]``).
PREVIEW_LIMIT = 10


def preview(rows: list) -> list:
    """Return the preview slice of ``rows``.

    Mirrors the production endpoint ``get_file_preview`` in
    ``app/api/v1/data.py``, which computes ``preview_rows = result.rows[:10]``.
    That ``[:10]`` slice is the source of truth for this behaviour.
    """
    return rows[:PREVIEW_LIMIT]


# Identifier-like cell characters: no CSV separators/quotes/whitespace, so each
# generated row serializes to an unambiguous, non-blank CSV line.
CELL_CHARS = string.ascii_letters + string.digits + "_-.@#%&+=:;"

# A fixed, small set of unique columns (2-3 columns satisfies the design hint
# and guarantees rows never collapse to a blank line).
COLUMNS = ["col_a", "col_b", "col_c"]

# Non-empty cell value with a safe alphabet.
cell_value = st.text(alphabet=CELL_CHARS, min_size=1, max_size=12)


def serialize_to_csv_bytes(columns: list[str], rows: list[list[str]]) -> bytes:
    """Serialize a table to CSV bytes (reuses the round-trip test pattern)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([str(cell) for cell in row])
    return buffer.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def datasets(draw: st.DrawFn) -> tuple[list[str], list[list[str]]]:
    """Generate a dataset with N rows over the fixed unique columns.

    ``N`` is varied across 0..30 so the preview is exercised below, at, and
    above ``PREVIEW_LIMIT`` (10).
    """
    n_cols = draw(st.integers(min_value=2, max_value=len(COLUMNS)))
    columns = COLUMNS[:n_cols]
    n_rows = draw(st.integers(min_value=0, max_value=30))
    rows = [
        draw(st.lists(cell_value, min_size=n_cols, max_size=n_cols))
        for _ in range(n_rows)
    ]
    return columns, rows


# ---------------------------------------------------------------------------
# Property tests — Property 4 (Req 2.2)
# ---------------------------------------------------------------------------


class TestDataPreviewRowCountProperties:
    """Property 4 — data preview returns exactly min(10, N) rows (Req 2.2)."""

    @given(dataset=datasets())
    @settings(deadline=None)
    def test_preview_returns_min_ten_parsed_rows(
        self, dataset: tuple[list[str], list[list[str]]]
    ) -> None:
        """Parsing N rows then slicing yields exactly min(10, N) preview rows.

        Exercises the real production path: ``parse_file(...)`` followed by the
        endpoint's ``result.rows[:10]`` slice.

        Validates: Requirements 2.2
        """
        columns, rows = dataset
        n = len(rows)
        csv_bytes = serialize_to_csv_bytes(columns, rows)

        result = parse_file(csv_bytes, "csv")

        # The parsed dataset has exactly N data rows.
        assert result.total_rows == n
        assert len(result.rows) == n

        preview_rows = preview(result.rows)

        expected_count = min(PREVIEW_LIMIT, n)
        # Core Property 4 invariant: exactly min(10, N) rows.
        assert len(preview_rows) == expected_count
        # The preview is the FIRST min(10, N) rows, in original order.
        assert preview_rows == result.rows[:expected_count]

    @given(rows=st.lists(st.integers(), max_size=40))
    @settings(deadline=None)
    def test_pure_preview_slice_row_count(self, rows: list[int]) -> None:
        """The pure slice logic returns min(10, N) for any list of length N.

        This makes the row-count invariant explicit for ALL N (including large
        N) independent of the parsing layer.

        Validates: Requirements 2.2
        """
        n = len(rows)
        result = preview(rows)

        assert len(result) == min(PREVIEW_LIMIT, n)
        assert result == rows[: min(PREVIEW_LIMIT, n)]


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestDataPreviewRowCountExamples:
    """Representative example-based regressions for Property 4 (Req 2.2)."""

    def test_zero_rows_via_parse(self) -> None:
        """A header-only dataset (N=0) yields an empty preview."""
        csv_bytes = serialize_to_csv_bytes(["col_a", "col_b"], [])

        result = parse_file(csv_bytes, "csv")

        assert result.total_rows == 0
        assert len(preview(result.rows)) == 0

    def test_one_row_via_parse(self) -> None:
        """A single-row dataset (N=1) yields a single preview row."""
        rows = [["v1", "v2"]]
        csv_bytes = serialize_to_csv_bytes(["col_a", "col_b"], rows)

        result = parse_file(csv_bytes, "csv")

        assert result.total_rows == 1
        preview_rows = preview(result.rows)
        assert len(preview_rows) == 1
        assert preview_rows == result.rows[:1]

    def test_eleven_rows_via_parse_caps_at_ten(self) -> None:
        """A dataset with N=11 rows yields exactly 10 preview rows (the first 10)."""
        rows = [[f"a{i}", f"b{i}"] for i in range(11)]
        csv_bytes = serialize_to_csv_bytes(["col_a", "col_b"], rows)

        result = parse_file(csv_bytes, "csv")

        assert result.total_rows == 11
        preview_rows = preview(result.rows)
        assert len(preview_rows) == PREVIEW_LIMIT
        assert preview_rows == result.rows[:PREVIEW_LIMIT]
        # First preview row is the first data row, in original order.
        assert preview_rows[0] == {"col_a": "a0", "col_b": "b0"}
        assert preview_rows[-1] == {"col_a": "a9", "col_b": "b9"}

    def test_pure_preview_representative_counts(self) -> None:
        """Pure helper returns min(10, N) for representative N values."""
        cases = {0: 0, 1: 1, 9: 9, 10: 10, 11: 10, 25: 10}
        for n, expected in cases.items():
            lst = list(range(n))
            assert len(preview(lst)) == expected
            assert preview(lst) == lst[:expected]
