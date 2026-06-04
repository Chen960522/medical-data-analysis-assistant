"""Property-based tests for data quality summary accuracy.

Validates: Requirements 2.4, 2.6
Property 6: 数据质量摘要准确性 (Data quality summary accuracy)

    For any dataset with known row count, column count and missing-value
    positions, the total rows, total columns and missing-value percentage
    reported in the quality summary SHALL exactly match the actual values.

The production implementation in ``app/services/data_parser.py`` is the source
of truth. The relevant computations are (EXACT):

  * ``total_rows = len(rows)``, ``total_columns = len(columns)``.
  * ``total_cells = total_rows * total_columns`` (``0`` when no columns).
  * ``overall_percentage = round(total_missing / total_cells * 100, 2)`` when
    ``total_cells > 0`` else ``0.0``. ``QualitySummary.missing_value_percentage``
    equals this rounded value.
  * ``completeness_score = round((total_cells - total_missing) / total_cells
    * 100, 2)`` when ``total_cells > 0`` else ``100.0``.
  * Per-column missing counts / positions are tracked; a key absent from a row
    dict counts as missing for that column.

A cell is "missing" per ``_is_missing`` when the value is ``None``, an
empty/whitespace-only string (``str.strip() == ""``) or a float ``NaN``.

Strategy design: every dataset is generated with a KNOWN structure so the test
can INDEPENDENTLY count missing cells and compute the expected metrics. Each
cell is drawn as EITHER a clearly-present value (non-empty/non-blank string, or
a non-NaN/non-inf number) OR a clearly-missing value (``None`` / ``""`` /
whitespace / ``NaN`` / omitted key). NaN is intentionally used ONLY as a
missing value because ``_is_missing`` treats float NaN as missing.
"""

import math
import string
from dataclasses import dataclass, field
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.data_parser import detect_missing_values, generate_quality_summary

# ---------------------------------------------------------------------------
# Helpers mirroring the production ``_is_missing`` contract
# ---------------------------------------------------------------------------


def _is_missing_value(value: Any) -> bool:
    """Local mirror of ``_is_missing`` for sanity-checking generators."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


# ---------------------------------------------------------------------------
# Cell-value strategies (unambiguous present vs. missing categories)
# ---------------------------------------------------------------------------

# Present values: never treated as missing by ``_is_missing``.
#  * non-empty strings from a safe alphabet (no whitespace -> strip() != "")
#  * non-NaN, non-inf numbers (NaN would otherwise count as missing)
present_value = st.one_of(
    st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=12),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
)

# Missing sentinels: exactly the cases ``_is_missing`` treats as missing.
missing_value = st.sampled_from([None, "", "   ", "\t", " \n ", float("nan")])

# Identifier-like, unique column names.
column_name = st.text(alphabet=string.ascii_letters, min_size=1, max_size=8)

# Sanity nets: keep the two categories strictly separated.
assert not _is_missing_value("a1")
assert _is_missing_value(None) and _is_missing_value("") and _is_missing_value("   ")
assert _is_missing_value(float("nan"))


@dataclass
class KnownDataset:
    """A generated dataset together with independently-computed expectations."""

    columns: list[str]
    rows: list[dict[str, Any]]
    num_rows: int
    num_cols: int
    total_missing: int
    per_column_missing: dict[str, int]
    missing_positions: set[tuple[int, str]] = field(default_factory=set)

    @property
    def total_cells(self) -> int:
        return self.num_rows * self.num_cols if self.num_cols > 0 else 0

    @property
    def expected_pct(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return round(self.total_missing / self.total_cells * 100, 2)

    @property
    def expected_completeness(self) -> float:
        if self.total_cells == 0:
            return 100.0
        return round((self.total_cells - self.total_missing) / self.total_cells * 100, 2)


@st.composite
def known_datasets(draw: st.DrawFn, allow_omission: bool = False) -> KnownDataset:
    """Generate a dataset with KNOWN missing-cell positions.

    Each cell is independently flagged present/missing; missing cells use a
    ``_is_missing`` sentinel (or, when ``allow_omission`` is set, the key may be
    omitted from the row dict entirely -- which also counts as missing).
    """
    num_cols = draw(st.integers(min_value=1, max_value=6))
    columns = draw(
        st.lists(column_name, min_size=num_cols, max_size=num_cols, unique=True)
    )
    num_rows = draw(st.integers(min_value=0, max_value=40))

    rows: list[dict[str, Any]] = []
    per_column_missing: dict[str, int] = {col: 0 for col in columns}
    missing_positions: set[tuple[int, str]] = set()
    total_missing = 0

    for row_idx in range(num_rows):
        row: dict[str, Any] = {}
        for col in columns:
            if draw(st.booleans()):  # this cell is MISSING
                total_missing += 1
                per_column_missing[col] += 1
                missing_positions.add((row_idx, col))
                # Optionally omit the key entirely (still counts as missing).
                if allow_omission and draw(st.booleans()):
                    continue
                row[col] = draw(missing_value)
            else:  # this cell is PRESENT
                row[col] = draw(present_value)
        rows.append(row)

    return KnownDataset(
        columns=columns,
        rows=rows,
        num_rows=num_rows,
        num_cols=num_cols,
        total_missing=total_missing,
        per_column_missing=per_column_missing,
        missing_positions=missing_positions,
    )


# ---------------------------------------------------------------------------
# Property tests -- Property 6 (Req 2.4, 2.6)
# ---------------------------------------------------------------------------


class TestQualitySummaryProperties:
    """Property 6 -- the quality summary exactly matches the actuals."""

    @given(dataset=known_datasets())
    @settings(deadline=None, max_examples=200)
    def test_summary_counts_and_percentage_match(self, dataset: KnownDataset) -> None:
        """Reported rows, columns and missing% match the known values.

        Validates: Requirements 2.6
        """
        summary = generate_quality_summary(dataset.columns, dataset.rows)

        assert summary.total_rows == dataset.num_rows
        assert summary.total_columns == dataset.num_cols
        assert summary.missing_value_percentage == dataset.expected_pct
        assert summary.completeness_score == dataset.expected_completeness

    @given(dataset=known_datasets())
    @settings(deadline=None, max_examples=200)
    def test_per_column_missing_counts_match(self, dataset: KnownDataset) -> None:
        """Each column's reported missing_count matches the known per-column count.

        Validates: Requirements 2.4
        """
        summary = generate_quality_summary(dataset.columns, dataset.rows)

        assert len(summary.columns) == dataset.num_cols
        assert [c.name for c in summary.columns] == dataset.columns
        for info in summary.columns:
            assert info.missing_count == dataset.per_column_missing[info.name]

    @given(dataset=known_datasets())
    @settings(deadline=None, max_examples=200)
    def test_detect_missing_values_matches_known(self, dataset: KnownDataset) -> None:
        """detect_missing_values reproduces the known totals and positions.

        Validates: Requirements 2.4
        """
        report = detect_missing_values(dataset.columns, dataset.rows)

        assert report.total_missing == dataset.total_missing
        assert report.total_cells == dataset.total_cells
        assert report.overall_percentage == dataset.expected_pct
        # Every generated missing position is reported, with no extras/dupes.
        assert set(report.positions) == dataset.missing_positions
        assert len(report.positions) == dataset.total_missing

    @given(dataset=known_datasets(allow_omission=True))
    @settings(deadline=None, max_examples=200)
    def test_omitted_keys_counted_as_missing(self, dataset: KnownDataset) -> None:
        """A key absent from a row dict is counted as missing everywhere.

        Validates: Requirements 2.4, 2.6
        """
        summary = generate_quality_summary(dataset.columns, dataset.rows)
        report = detect_missing_values(dataset.columns, dataset.rows)

        assert summary.total_rows == dataset.num_rows
        assert summary.total_columns == dataset.num_cols
        assert summary.missing_value_percentage == dataset.expected_pct
        assert report.total_missing == dataset.total_missing
        assert set(report.positions) == dataset.missing_positions
        for info in summary.columns:
            assert info.missing_count == dataset.per_column_missing[info.name]


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestQualitySummaryExamples:
    """Representative example-based regressions for Property 6 (Req 2.4, 2.6)."""

    def test_two_missing_of_four_cells_is_fifty_percent(self) -> None:
        """2 missing of 4 cells -> 50.0% missing, 50.0% complete (Req 2.6)."""
        columns = ["a", "b"]
        rows = [
            {"a": 1, "b": None},
            {"a": "", "b": 2},
        ]
        summary = generate_quality_summary(columns, rows)
        assert summary.total_rows == 2
        assert summary.total_columns == 2
        assert summary.missing_value_percentage == 50.0
        assert summary.completeness_score == 50.0

    def test_two_missing_of_six_cells_rounds_to_thirty_three_thirty_three(self) -> None:
        """2 missing of 6 cells -> round(33.333.., 2) == 33.33 (Req 2.6)."""
        columns = ["a", "b", "c"]
        rows = [
            {"a": 1, "b": "x", "c": None},
            {"a": "   ", "b": "y", "c": 3},
        ]
        summary = generate_quality_summary(columns, rows)
        assert summary.total_rows == 2
        assert summary.total_columns == 3
        assert summary.missing_value_percentage == 33.33
        assert summary.completeness_score == 66.67

    def test_all_missing_dataset_is_hundred_percent(self) -> None:
        """An all-missing dataset reports 100.0% missing, 0.0% complete (Req 2.4)."""
        columns = ["a", "b"]
        rows = [
            {"a": None, "b": ""},
            {"a": "  ", "b": float("nan")},
        ]
        summary = generate_quality_summary(columns, rows)
        assert summary.missing_value_percentage == 100.0
        assert summary.completeness_score == 0.0
        for info in summary.columns:
            assert info.missing_count == 2

    def test_no_missing_dataset_is_zero_percent(self) -> None:
        """A fully-populated dataset reports 0.0% missing, 100.0% complete (Req 2.6)."""
        columns = ["a", "b"]
        rows = [
            {"a": 1, "b": "x"},
            {"a": 2.5, "b": "y"},
        ]
        summary = generate_quality_summary(columns, rows)
        assert summary.missing_value_percentage == 0.0
        assert summary.completeness_score == 100.0
        for info in summary.columns:
            assert info.missing_count == 0

    def test_empty_dataset_zero_rows(self) -> None:
        """Zero rows -> 0 rows, 0.0% missing, 100.0% complete (Req 2.6)."""
        columns = ["a", "b", "c"]
        rows: list[dict[str, Any]] = []
        summary = generate_quality_summary(columns, rows)
        assert summary.total_rows == 0
        assert summary.total_columns == 3
        assert summary.missing_value_percentage == 0.0
        assert summary.completeness_score == 100.0

    def test_single_column_with_missing(self) -> None:
        """A single-column dataset reports the correct per-column count (Req 2.4)."""
        columns = ["only"]
        rows = [{"only": "v"}, {"only": None}, {"only": "w"}, {"only": ""}]
        summary = generate_quality_summary(columns, rows)
        assert summary.total_columns == 1
        # 2 missing of 4 cells -> 50%
        assert summary.missing_value_percentage == 50.0
        assert summary.columns[0].missing_count == 2

    def test_omitted_key_counts_as_missing(self) -> None:
        """A row missing a key entirely is counted as missing (Req 2.4)."""
        columns = ["a", "b"]
        rows = [
            {"a": 1, "b": 2},
            {"a": 3},  # "b" omitted -> missing
        ]
        report = detect_missing_values(columns, rows)
        assert report.total_missing == 1
        assert (1, "b") in report.positions
        summary = generate_quality_summary(columns, rows)
        assert summary.missing_value_percentage == 25.0

    def test_nan_is_only_used_as_missing(self) -> None:
        """Guard: NaN counts as missing while other floats are present (Req 2.4)."""
        # Documents why numeric present values exclude NaN in the generators.
        assert _is_missing_value(float("nan"))
        assert not _is_missing_value(0.0)
        assert not _is_missing_value(-3.5)
