"""Property-based tests for column data-type detection.

Validates: Requirements 2.3
Property 5: 列类型检测正确性 (Column type detection correctness)

    For any column composed of known single-type data (pure numeric, pure
    date, pure categorical values), the type detector SHALL correctly identify
    the column's data type.

The production implementation in ``app/services/data_parser.py`` is the source
of truth. ``detect_column_types(columns, rows)`` delegates per column to
``_detect_single_column_type(values)``, which decides as follows (the ORDER
matters and defines the exact domain where this property holds):

  1. Null/blank values (``None`` / whitespace-only) are dropped. An all-blank
     column is ``"text"``.
  2. The first 100 non-null values form the ``sample`` (``sample_size``).
  3. NUMERIC is checked FIRST: a value counts as numeric when it is an
     ``int``/``float`` instance OR a string that ``float(v)`` accepts. If
     ``numeric_count > 0.8 * sample_size`` the column is ``"numeric"``.
  4. DATE next: a value counts as a date when it is a ``datetime``/``date``
     instance OR a string matching one of the date regexes
     (``YYYY-MM-DD`` / ``YYYY/MM/DD`` / ``DD-MM-YYYY`` / ``YYYY.MM.DD``). If
     ``date_count > 0.8 * sample_size`` the column is ``"date"``.
  5. CATEGORICAL next: if ``len(set(str(v))) / sample_size < 0.3`` (low
     cardinality) the column is ``"categorical"``.
  6. Otherwise the column is ``"text"``.

Domain restrictions for each "pure" generator (so the property holds):

  * Pure numeric: every value is a number or a numeric string, so
    ``numeric_count == sample_size`` and numeric wins outright.
  * Pure date: every value is a dash/slash date string. Such strings are NOT
    ``float``-parseable (so they never count as numeric), and they DO match the
    date regexes, so date wins.
  * Pure categorical: alphabetic, low-cardinality labels that are neither
    ``float``-parseable (excludes ``inf``/``nan``) nor date-shaped, built
    deterministically so the distinct-ratio is always ``< 0.3``.
  * Text (complementary): many DISTINCT alphabetic, non-numeric, non-date
    strings, so the distinct-ratio is ``>= 0.3`` and the residual ``"text"``
    branch is taken.
"""

import datetime
import math
import string
from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.services.data_parser import detect_column_types

# ---------------------------------------------------------------------------
# Helpers (mirror the detector's notion of "numeric" / "date" tokens)
# ---------------------------------------------------------------------------


def _is_float_parseable(value: str) -> bool:
    """True when ``float(value)`` would succeed (e.g. ``"3"``, ``"inf"``)."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


# A pool of clean alphabetic labels: none are ``float``-parseable (no
# ``inf``/``nan``) and none can match a date regex (the regexes all start with
# a digit). Used to build categorical / text columns safely.
CATEGORY_WORDS = [
    "active",
    "inactive",
    "pending",
    "mild",
    "moderate",
    "severe",
    "positive",
    "negative",
    "low",
    "high",
    "normal",
    "abnormal",
]

# Sanity check: keep the pool strictly inside the categorical/text domain.
assert all(not _is_float_parseable(w) for w in CATEGORY_WORDS)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# A single "pure numeric" cell: native int/float OR their string forms. Every
# such value is counted as numeric by the detector.
numeric_value = st.one_of(
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.integers(min_value=-1_000_000, max_value=1_000_000).map(str),
    st.floats(allow_nan=False, allow_infinity=False, width=32).map(str),
)


@st.composite
def pure_numeric_columns(draw: st.DrawFn) -> list[Any]:
    """A non-empty column whose every value is numeric (int/float/str)."""
    return draw(st.lists(numeric_value, min_size=1, max_size=30))


@st.composite
def pure_date_columns(draw: st.DrawFn) -> list[str]:
    """A non-empty column of valid ``YYYY-MM-DD`` / ``YYYY/MM/DD`` date strings.

    Date strings contain ``-``/``/`` separators, so ``float()`` rejects them
    (never numeric), and they match the detector's date regex.
    """
    dates = draw(st.lists(st.dates(), min_size=1, max_size=30))
    use_slash = draw(st.booleans())
    fmt = "%Y/%m/%d" if use_slash else "%Y-%m-%d"
    return [d.strftime(fmt) for d in dates]


@st.composite
def pure_categorical_columns(draw: st.DrawFn) -> list[str]:
    """A low-cardinality column of alphabetic labels (distinct ratio < 0.3).

    Construction is deterministic: pick ``num_categories`` distinct labels and
    cycle them across ``n`` rows where ``num_categories / n < 0.3``. Because the
    labels are alphabetic words from :data:`CATEGORY_WORDS` they are neither
    numeric nor date-shaped, so the categorical branch is taken.
    """
    num_categories = draw(st.integers(min_value=2, max_value=3))
    categories = draw(
        st.lists(
            st.sampled_from(CATEGORY_WORDS),
            min_size=num_categories,
            max_size=num_categories,
            unique=True,
        )
    )
    # n strictly greater than num_categories / 0.3 guarantees ratio < 0.3.
    # num_categories <= 3 -> n >= 11 is always sufficient (3 / 11 ~= 0.27).
    n = draw(st.integers(min_value=11, max_value=60))
    values = [categories[i % num_categories] for i in range(n)]
    # Safety net: the distinct ratio must stay inside the categorical domain.
    assert len(set(values)) / n < 0.3
    return values


@st.composite
def high_cardinality_text_columns(draw: st.DrawFn) -> list[str]:
    """A column of many DISTINCT alphabetic, non-numeric, non-date strings.

    All values distinct -> distinct ratio is 1.0 (>= 0.3); alphabetic words
    never match a date regex; ``inf``/``nan``-like tokens are filtered out, so
    the residual ``"text"`` branch is taken.
    """
    words = draw(
        st.lists(
            st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=10),
            min_size=4,
            max_size=30,
            unique=True,
        )
    )
    # Exclude the only alphabetic tokens float() accepts (inf/nan/infinity).
    assume(all(not _is_float_parseable(w) for w in words))
    return words


@st.composite
def mixed_type_tables(
    draw: st.DrawFn,
) -> tuple[list[str], list[dict[str, Any]]]:
    """A table with one numeric, one date and one categorical column.

    All three columns share the same row count so they can live in a single
    ``rows`` list, mirroring ``test_detect_multiple_columns`` in
    ``tests/test_data_parser.py``.
    """
    n = draw(st.integers(min_value=11, max_value=40))

    numeric_vals = [draw(numeric_value) for _ in range(n)]

    base_dates = draw(st.lists(st.dates(), min_size=n, max_size=n))
    date_vals = [d.strftime("%Y-%m-%d") for d in base_dates]

    num_categories = draw(st.integers(min_value=2, max_value=3))
    categories = draw(
        st.lists(
            st.sampled_from(CATEGORY_WORDS),
            min_size=num_categories,
            max_size=num_categories,
            unique=True,
        )
    )
    cat_vals = [categories[i % num_categories] for i in range(n)]

    columns = ["measure", "visit_date", "status"]
    rows = [
        {"measure": numeric_vals[i], "visit_date": date_vals[i], "status": cat_vals[i]}
        for i in range(n)
    ]
    return columns, rows


# ---------------------------------------------------------------------------
# Property tests — Property 5 (Req 2.3)
# ---------------------------------------------------------------------------


class TestColumnTypeDetectionProperties:
    """Property 5 — pure single-type columns are classified correctly (Req 2.3)."""

    @given(values=pure_numeric_columns())
    @settings(deadline=None)
    def test_pure_numeric_column_detected_as_numeric(self, values: list[Any]) -> None:
        """A column of only numeric values is detected as ``"numeric"``.

        Validates: Requirements 2.3
        """
        rows = [{"col": v} for v in values]
        assert detect_column_types(["col"], rows)["col"] == "numeric"

    @given(values=pure_date_columns())
    @settings(deadline=None)
    def test_pure_date_column_detected_as_date(self, values: list[str]) -> None:
        """A column of only valid date strings is detected as ``"date"``.

        Validates: Requirements 2.3
        """
        rows = [{"col": v} for v in values]
        assert detect_column_types(["col"], rows)["col"] == "date"

    @given(values=pure_categorical_columns())
    @settings(deadline=None)
    def test_pure_categorical_column_detected_as_categorical(
        self, values: list[str]
    ) -> None:
        """A low-cardinality label column is detected as ``"categorical"``.

        Validates: Requirements 2.3
        """
        rows = [{"col": v} for v in values]
        assert detect_column_types(["col"], rows)["col"] == "categorical"

    @given(values=high_cardinality_text_columns())
    @settings(deadline=None)
    def test_high_cardinality_strings_detected_as_text(
        self, values: list[str]
    ) -> None:
        """Many distinct non-numeric/non-date strings fall through to ``"text"``.

        Validates: Requirements 2.3
        """
        rows = [{"col": v} for v in values]
        assert detect_column_types(["col"], rows)["col"] == "text"

    @given(table=mixed_type_tables())
    @settings(deadline=None)
    def test_multiple_columns_each_detected_independently(
        self, table: tuple[list[str], list[dict[str, Any]]]
    ) -> None:
        """A numeric + date + categorical table classifies every column.

        Validates: Requirements 2.3
        """
        columns, rows = table
        types = detect_column_types(columns, rows)
        assert types["measure"] == "numeric"
        assert types["visit_date"] == "date"
        assert types["status"] == "categorical"


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


class TestColumnTypeDetectionExamples:
    """Representative example-based regressions for Property 5 (Req 2.3)."""

    def test_pure_numeric_example(self) -> None:
        """Fixed numeric column (mixed int/float/str) -> ``"numeric"`` (Req 2.3)."""
        columns = ["glucose"]
        rows = [
            {"glucose": 5.4},
            {"glucose": 6},
            {"glucose": "7.1"},
            {"glucose": "8"},
            {"glucose": -2.5},
        ]
        assert detect_column_types(columns, rows)["glucose"] == "numeric"

    def test_pure_date_iso_example(self) -> None:
        """Fixed ISO date column -> ``"date"`` (Req 2.3)."""
        columns = ["visit_date"]
        rows = [
            {"visit_date": "2024-01-01"},
            {"visit_date": "2024-02-15"},
            {"visit_date": "2024-03-20"},
            {"visit_date": "2024-04-10"},
            {"visit_date": "2024-05-05"},
        ]
        assert detect_column_types(columns, rows)["visit_date"] == "date"

    def test_pure_date_slash_example(self) -> None:
        """Fixed slash date column -> ``"date"`` (Req 2.3)."""
        columns = ["visit_date"]
        rows = [
            {"visit_date": "2024/01/01"},
            {"visit_date": "2024/02/15"},
            {"visit_date": "2024/03/20"},
            {"visit_date": "2024/04/10"},
            {"visit_date": "2024/05/05"},
        ]
        assert detect_column_types(columns, rows)["visit_date"] == "date"

    def test_pure_categorical_example(self) -> None:
        """Fixed low-cardinality column -> ``"categorical"`` (Req 2.3)."""
        columns = ["status"]
        # 12 rows, 2 distinct values -> ratio = 2/12 ~= 0.17 < 0.3
        rows = [{"status": "active"} for _ in range(6)] + [
            {"status": "inactive"} for _ in range(6)
        ]
        assert detect_column_types(columns, rows)["status"] == "categorical"

    def test_native_date_objects_example(self) -> None:
        """Native ``date`` objects are detected as ``"date"`` (Req 2.3)."""
        columns = ["visit_date"]
        rows = [
            {"visit_date": datetime.date(2024, 1, 1)},
            {"visit_date": datetime.date(2024, 2, 1)},
            {"visit_date": datetime.date(2024, 3, 1)},
            {"visit_date": datetime.date(2024, 4, 1)},
            {"visit_date": datetime.date(2024, 5, 1)},
        ]
        assert detect_column_types(columns, rows)["visit_date"] == "date"

    def test_text_example(self) -> None:
        """High-cardinality free text -> ``"text"`` (Req 2.3)."""
        columns = ["note"]
        rows = [
            {"note": "patient shows improvement"},
            {"note": "no significant changes"},
            {"note": "mild symptoms observed"},
            {"note": "treatment ongoing"},
            {"note": "followup required"},
        ]
        assert detect_column_types(columns, rows)["note"] == "text"

    def test_mixed_columns_example(self) -> None:
        """A numeric + date + categorical table classifies each column (Req 2.3)."""
        columns = ["measure", "visit_date", "status"]
        statuses = ["active", "inactive", "pending"]
        rows = [
            {
                "measure": float(i),
                "visit_date": f"2024-01-{(i % 28) + 1:02d}",
                "status": statuses[i % 3],
            }
            for i in range(12)
        ]
        types = detect_column_types(columns, rows)
        assert types["measure"] == "numeric"
        assert types["visit_date"] == "date"
        assert types["status"] == "categorical"

    def test_helper_excludes_inf_nan_tokens(self) -> None:
        """Guard: ``inf``/``nan`` are float-parseable and must be excluded.

        Documents why the categorical/text generators avoid these alphabetic
        tokens (they would otherwise be counted as numeric).
        """
        assert _is_float_parseable("inf")
        assert _is_float_parseable("nan")
        assert math.isnan(float("nan"))
        assert not _is_float_parseable("active")
