"""Property-based tests for data-parsing round-trip consistency.

Validates: Requirements 2.1
Property 3: 数据解析往返一致性 (Data parsing round-trip consistency)

    For any valid structured tabular data (with numeric, text, and date type
    columns), serializing it to CSV format and then parsing it back SHALL
    produce structured data equivalent to the original.

The production implementation in ``app/services/data_parser.py`` is the source
of truth for what "equivalent" means here:

  * ``parse_file(content, "csv")`` decodes the bytes as UTF-8 (BOM tolerant)
    and reads them with ``csv.DictReader``. ``DictReader`` consumes the first
    line as the header (column names) and returns EVERY cell value as a
    ``str``. Numbers and dates therefore come back as their *string* forms.
  * ``ParseResult`` exposes ``columns`` (header order preserved), ``rows``
    (list of ``{column: str_value}`` dicts), ``total_rows`` (number of data
    rows) and ``total_columns`` (``len(columns)``).

Because ``DictReader`` yields strings, the round-trip is checked against the
``str(...)`` form of each original cell — exactly how the cell was written to
the CSV. The expected dict for every row is built with the same ``str(...)``
serialization used to produce the CSV bytes.

Domain of valid inputs for the round-trip property (documented restrictions):

  * Column names are UNIQUE (``csv.DictReader`` collapses duplicate header
    names, so duplicates cannot round-trip unambiguously) and drawn from a safe
    alphabet (ASCII letters, digits, underscore). They are non-empty and carry
    no commas, quotes, whitespace or line breaks, so the header line is
    unambiguous.
  * Text cells are drawn from a safe alphabet that excludes ``,`` ``"`` ``\r``
    ``\n`` and whitespace, and are non-empty. This keeps the CSV writing
    unambiguous and avoids the one genuine round-trip edge in ``csv``: a
    single-column row whose only value is empty serializes to a blank line,
    which ``DictReader`` SKIPS. Numbers/dates always ``str()`` to a non-empty
    token, so every generated row serializes to a non-blank line.
  * Floats exclude NaN/Infinity. Every row has exactly one value per column, so
    no trailing field is dropped (which would surface as ``None``).

Multi-column tables containing empty-string cells DO round-trip correctly (an
empty field between commas parses back to ``""``); this is covered by an
example-based regression test below.
"""

import csv
import datetime
import io
import string
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_parser import parse_file

# ---------------------------------------------------------------------------
# Safe alphabets (see the module docstring for why each is restricted)
# ---------------------------------------------------------------------------

# Column-name characters: identifier-like, no separators/quotes/whitespace.
COLUMN_NAME_CHARS = string.ascii_letters + string.digits + "_"

# Text-cell characters: printable, no CSV separators/quotes/whitespace so the
# round-trip is exact without relying on csv quoting behaviour.
TEXT_CELL_CHARS = string.ascii_letters + string.digits + "_-.@#%&+=:;"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

column_name = st.text(alphabet=COLUMN_NAME_CHARS, min_size=1, max_size=12)

# A single cell value covering the numeric / text / date column types named in
# Property 3. These are the *original* values; they are serialized with str().
cell_value = st.one_of(
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(alphabet=TEXT_CELL_CHARS, min_size=1, max_size=20),
    st.dates(),
)


@st.composite
def tables(draw: st.DrawFn) -> tuple[list[str], list[list[Any]]]:
    """Generate a valid structured table: unique columns + fully-populated rows.

    Returns ``(column_names, rows)`` where ``rows`` is a list of cell lists,
    each of length ``len(column_names)``.
    """
    column_names = draw(
        st.lists(column_name, min_size=1, max_size=6, unique=True)
    )
    n_cols = len(column_names)
    n_rows = draw(st.integers(min_value=0, max_value=8))
    rows = [
        draw(st.lists(cell_value, min_size=n_cols, max_size=n_cols))
        for _ in range(n_rows)
    ]
    return column_names, rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def serialize_to_csv_bytes(column_names: list[str], rows: list[list[Any]]) -> bytes:
    """Serialize a table to CSV bytes the way a valid CSV file would look.

    Each cell is written via ``str(...)`` — mirroring how the value would be
    rendered to text — using ``\n`` line endings to match the inputs the parser
    is exercised with elsewhere.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(column_names)
    for row in rows:
        writer.writerow([str(cell) for cell in row])
    return buffer.getvalue().encode("utf-8")


def expected_row(column_names: list[str], row: list[Any]) -> dict[str, str]:
    """Build the expected parsed dict: column -> str(original cell)."""
    return {col: str(cell) for col, cell in zip(column_names, row)}


# ---------------------------------------------------------------------------
# Property test — Property 3 (Req 2.1)
# ---------------------------------------------------------------------------


class TestDataParsingRoundTripProperties:
    """Property 3 — CSV serialize/parse round-trip consistency (Req 2.1)."""

    @given(table=tables())
    @settings(deadline=None)
    def test_csv_roundtrip_preserves_structured_data(
        self, table: tuple[list[str], list[list[Any]]]
    ) -> None:
        """Serializing a table to CSV then parsing it reproduces the structure.

        Validates: Requirements 2.1
        """
        column_names, rows = table
        csv_bytes = serialize_to_csv_bytes(column_names, rows)

        result = parse_file(csv_bytes, "csv")

        # Header order and counts are preserved exactly.
        assert result.columns == column_names
        assert result.total_columns == len(column_names)
        assert result.total_rows == len(rows)
        assert len(result.rows) == len(rows)

        # Each parsed row equals the str()-serialized form of the original row.
        for original, parsed in zip(rows, result.rows):
            assert parsed == expected_row(column_names, original)


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestDataParsingRoundTripExamples:
    """Representative example-based regressions for Property 3 (Req 2.1)."""

    def test_numeric_text_date_columns_roundtrip(self) -> None:
        """A small mixed numeric/text/date table round-trips to string forms."""
        columns = ["patient_id", "name", "glucose", "visit_date"]
        rows = [
            [1, "Alice", 5.4, datetime.date(2023, 1, 15)],
            [2, "Bob", 6.1, datetime.date(2023, 2, 20)],
            [3, "Charlie", 4.9, datetime.date(2023, 3, 10)],
        ]
        csv_bytes = serialize_to_csv_bytes(columns, rows)

        result = parse_file(csv_bytes, "csv")

        assert result.columns == columns
        assert result.total_columns == 4
        assert result.total_rows == 3
        assert result.rows[0] == {
            "patient_id": "1",
            "name": "Alice",
            "glucose": "5.4",
            "visit_date": "2023-01-15",
        }
        assert result.rows[2] == {
            "patient_id": "3",
            "name": "Charlie",
            "glucose": "4.9",
            "visit_date": "2023-03-10",
        }

    def test_single_column_roundtrip(self) -> None:
        """A single-column table round-trips with the column preserved."""
        columns = ["measurement"]
        rows = [[10], [20], [30]]
        csv_bytes = serialize_to_csv_bytes(columns, rows)

        result = parse_file(csv_bytes, "csv")

        assert result.columns == ["measurement"]
        assert result.total_columns == 1
        assert result.total_rows == 3
        assert [r["measurement"] for r in result.rows] == ["10", "20", "30"]

    def test_single_row_roundtrip(self) -> None:
        """A single data row round-trips exactly."""
        columns = ["a", "b", "c"]
        rows = [["x", 1, datetime.date(2020, 12, 31)]]
        csv_bytes = serialize_to_csv_bytes(columns, rows)

        result = parse_file(csv_bytes, "csv")

        assert result.total_rows == 1
        assert result.rows[0] == {"a": "x", "b": "1", "c": "2020-12-31"}

    def test_header_only_zero_rows_roundtrip(self) -> None:
        """A header-only table parses to zero rows with columns preserved."""
        columns = ["col1", "col2", "col3"]
        csv_bytes = serialize_to_csv_bytes(columns, [])

        result = parse_file(csv_bytes, "csv")

        assert result.columns == columns
        assert result.total_columns == 3
        assert result.total_rows == 0
        assert result.rows == []

    def test_multicolumn_empty_string_cells_roundtrip(self) -> None:
        """Empty-string cells in a multi-column table round-trip to ``""``.

        (An empty field between separators parses back to an empty string; only
        a single-column all-empty row would be dropped, which the property's
        domain excludes.)
        """
        columns = ["a", "b"]
        rows = [["", "x"], ["y", ""]]
        csv_bytes = serialize_to_csv_bytes(columns, rows)

        result = parse_file(csv_bytes, "csv")

        assert result.total_rows == 2
        assert result.rows[0] == {"a": "", "b": "x"}
        assert result.rows[1] == {"a": "y", "b": ""}
