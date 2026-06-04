"""Property-based tests for literature search result sorting.

Validates: Requirements 10.24
Property 18: 搜索结果排序正确性 (Search result sorting correctness)

    For any literature search result list and sort criterion (by date or by
    citation count), the sorted list SHALL satisfy: for any two adjacent
    elements in the list, the sort-field value of the earlier element is >=
    that of the later element.

The production implementation in ``app/api/v1/literature.py`` is the source of
truth. ``_apply_sort(records, sort_by)`` decides as follows (these exact
semantics define the domain where the property holds):

  * ``sort_by == "date"``: ``sorted(records, key=lambda r: r.publication_date
    or "", reverse=True)``. ``None`` publication dates collapse to the empty
    string ``""`` (the smallest string), so they sink to the bottom. Dates are
    compared AS STRINGS (lexicographically); for zero-padded ``YYYY-MM-DD``
    values lexicographic order matches chronological order.
  * ``sort_by == "citations"``: ``sorted(records, key=lambda r: r.citation_count
    or 0, reverse=True)``. ``None`` citation counts collapse to ``0``.
  * any other value (``None`` / ``"relevance"`` / unknown): the input list is
    returned UNCHANGED (same objects in the same order).
  * ``sorted(...)`` is STABLE, so records with equal sort keys keep their
    original relative order.
"""

import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.v1.literature import _apply_sort
from app.schemas.literature import LiteratureRecord

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Canonical data-source labels the records carry ("CNKI" / "PubMed").
_DATA_SOURCES = ["CNKI", "PubMed"]

# A non-empty short title. Any text is fine; sorting never inspects the title.
_titles = st.text(min_size=1, max_size=20)

# publication_date: None OR a zero-padded YYYY-MM-DD string. For this format
# lexicographic (string) order equals chronological order, matching the
# implementation's string comparison.
_publication_dates = st.one_of(
    st.none(),
    st.dates().map(lambda d: d.strftime("%Y-%m-%d")),
)

# citation_count: None OR a non-negative bounded integer.
_citation_counts = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=10_000),
)


@st.composite
def literature_records(draw: st.DrawFn) -> LiteratureRecord:
    """A single :class:`LiteratureRecord` with sort-relevant fields varied."""
    return LiteratureRecord(
        title=draw(_titles),
        data_source=draw(st.sampled_from(_DATA_SOURCES)),
        publication_date=draw(_publication_dates),
        citation_count=draw(_citation_counts),
    )


@st.composite
def record_lists(draw: st.DrawFn) -> list[LiteratureRecord]:
    """A list (length 0..15) of literature records."""
    return draw(st.lists(literature_records(), min_size=0, max_size=15))


def _date_key(record: LiteratureRecord) -> str:
    """Mirror the implementation's date sort key (``None`` -> ``""``)."""
    return record.publication_date or ""


def _citation_key(record: LiteratureRecord) -> int:
    """Mirror the implementation's citation sort key (``None`` -> ``0``)."""
    return record.citation_count or 0


# ---------------------------------------------------------------------------
# Property tests — Property 18 (Req 10.24)
# ---------------------------------------------------------------------------


class TestSearchSortingProperties:
    """Property 18 — sorted results respect the adjacency invariant (Req 10.24)."""

    @given(records=record_lists())
    @settings(deadline=None)
    def test_sort_by_date_adjacency_invariant(
        self, records: list[LiteratureRecord]
    ) -> None:
        """Date sort: each element's date >= the next element's (Req 10.24).

        ``None`` dates collapse to ``""`` and compare as the smallest value.

        Validates: Requirements 10.24
        """
        result = _apply_sort(records, "date")
        for earlier, later in zip(result, result[1:]):
            assert _date_key(earlier) >= _date_key(later)

    @given(records=record_lists())
    @settings(deadline=None)
    def test_sort_by_citations_adjacency_invariant(
        self, records: list[LiteratureRecord]
    ) -> None:
        """Citation sort: each element's count >= the next element's (Req 10.24).

        ``None`` counts collapse to ``0``.

        Validates: Requirements 10.24
        """
        result = _apply_sort(records, "citations")
        for earlier, later in zip(result, result[1:]):
            assert _citation_key(earlier) >= _citation_key(later)

    @given(records=record_lists(), sort_by=st.sampled_from(["date", "citations"]))
    @settings(deadline=None)
    def test_sort_preserves_multiset_of_records(
        self, records: list[LiteratureRecord], sort_by: str
    ) -> None:
        """Sorting neither adds nor drops records (Req 10.24).

        The output is a permutation of the input: same length and exactly the
        same record objects. Object identity (``id``) is used because sorting
        only reorders the existing objects.

        Validates: Requirements 10.24
        """
        result = _apply_sort(records, sort_by)
        assert len(result) == len(records)
        assert sorted(id(r) for r in result) == sorted(id(r) for r in records)

    @given(records=record_lists(), sort_by=st.sampled_from(["date", "citations"]))
    @settings(deadline=None)
    def test_sort_is_stable_for_ties(
        self, records: list[LiteratureRecord], sort_by: str
    ) -> None:
        """Records sharing a sort key keep their input relative order (Req 10.24).

        Python's ``sorted`` is stable, so for any group of records with an equal
        key value their order in the output matches their order in the input.

        Validates: Requirements 10.24
        """
        key = _date_key if sort_by == "date" else _citation_key
        result = _apply_sort(records, sort_by)
        # For each distinct key value, the subsequence of matching records must
        # appear in the same relative order before and after sorting.
        for key_value in {key(r) for r in records}:
            before = [id(r) for r in records if key(r) == key_value]
            after = [id(r) for r in result if key(r) == key_value]
            assert before == after

    @given(
        records=record_lists(),
        sort_by=st.sampled_from([None, "relevance", "unknown"]),
    )
    @settings(deadline=None)
    def test_default_preserves_order(
        self, records: list[LiteratureRecord], sort_by: str | None
    ) -> None:
        """Default / relevance / unknown sort returns the list unchanged (Req 10.24).

        Validates: Requirements 10.24
        """
        result = _apply_sort(records, sort_by)
        assert [id(r) for r in result] == [id(r) for r in records]


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


def _record(
    title: str,
    *,
    publication_date: str | None = None,
    citation_count: int | None = None,
    data_source: str = "PubMed",
) -> LiteratureRecord:
    """Build a record with only the sort-relevant fields set."""
    return LiteratureRecord(
        title=title,
        data_source=data_source,
        publication_date=publication_date,
        citation_count=citation_count,
    )


class TestSearchSortingExamples:
    """Representative example-based regressions for Property 18 (Req 10.24)."""

    def test_sort_by_date_newest_first_with_none_sinking(self) -> None:
        """Known dates sort newest-first; ``None`` date sinks to the bottom (Req 10.24)."""
        records = [
            _record("a", publication_date="2022-05-01"),
            _record("b", publication_date=None),
            _record("c", publication_date="2024-01-15"),
            _record("d", publication_date="2023-12-31"),
        ]
        result = _apply_sort(records, "date")
        assert [r.title for r in result] == ["c", "d", "a", "b"]

    def test_sort_by_citations_desc_with_none_as_zero(self) -> None:
        """Known citation counts sort high-to-low; ``None`` treated as ``0`` (Req 10.24).

        "b" (``None`` -> 0) and "d" (0) tie at key 0; the stable sort keeps
        their input order ("b" precedes "d"), so "b" appears before "d".
        """
        records = [
            _record("a", citation_count=10),
            _record("b", citation_count=None),
            _record("c", citation_count=250),
            _record("d", citation_count=0),
            _record("e", citation_count=42),
        ]
        result = _apply_sort(records, "citations")
        assert [r.title for r in result] == ["c", "e", "a", "b", "d"]

    def test_sort_by_date_is_stable_for_equal_dates(self) -> None:
        """Equal-date records keep their input order (stable sort) (Req 10.24)."""
        records = [
            _record("first", publication_date="2024-01-01"),
            _record("second", publication_date="2024-01-01"),
            _record("third", publication_date="2024-01-01"),
        ]
        result = _apply_sort(records, "date")
        assert [r.title for r in result] == ["first", "second", "third"]

    def test_relevance_preserves_original_order(self) -> None:
        """``relevance`` returns the records untouched (Req 10.24)."""
        records = [
            _record("a", citation_count=1),
            _record("b", citation_count=999),
            _record("c", citation_count=50),
        ]
        result = _apply_sort(records, "relevance")
        assert result is records
        assert [r.title for r in result] == ["a", "b", "c"]

    def test_empty_list_for_each_sort_key(self) -> None:
        """Sorting an empty list yields an empty list for every key (Req 10.24)."""
        assert _apply_sort([], "date") == []
        assert _apply_sort([], "citations") == []
        assert _apply_sort([], "relevance") == []
        assert _apply_sort([], None) == []

    def test_single_element_for_each_sort_key(self) -> None:
        """A single-element list is trivially sorted for every key (Req 10.24)."""
        for sort_by in ("date", "citations", "relevance", None):
            record = _record("solo", publication_date="2024-06-01", citation_count=7)
            result = _apply_sort([record], sort_by)
            assert len(result) == 1
            assert result[0].title == "solo"

    def test_native_date_lexicographic_matches_chronological(self) -> None:
        """Zero-padded ``YYYY-MM-DD`` string order matches date order (Req 10.24).

        Documents why the generator formats ``st.dates()`` as ``%Y-%m-%d``: the
        implementation compares dates as strings, and this format keeps
        lexicographic order aligned with chronological order.
        """
        early = datetime.date(2023, 2, 9).strftime("%Y-%m-%d")  # "2023-02-09"
        late = datetime.date(2023, 11, 10).strftime("%Y-%m-%d")  # "2023-11-10"
        assert early < late  # string comparison agrees with chronology
        records = [_record("early", publication_date=early), _record("late", publication_date=late)]
        result = _apply_sort(records, "date")
        assert [r.title for r in result] == ["late", "early"]
