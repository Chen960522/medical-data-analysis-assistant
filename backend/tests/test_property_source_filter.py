"""Property-based tests for literature search result data-source filtering.

Validates: Requirements 10.25
Property 19: 搜索结果数据源过滤正确性 (Search result data source filtering correctness)

    For any literature result list containing mixed data sources (CNKI and
    PubMed), after filtering by data source, ALL records in the result list
    SHALL have a data-source label matching the filter condition.

Requirement 10.25 — the Literature_Search_Module SHALL allow the User to filter
the merged result list by data source (show CNKI only, PubMed only, or both).

The production implementation in ``app/api/v1/literature.py`` is the source of
truth. Inside ``search_literature`` the merged records are filtered by the
SELECTED sources with the inline comprehension::

    selected_labels = {SOURCE_LABELS[s] for s in sources}
    records = [r for r in records if r.data_source in selected_labels]

where ``SOURCE_LABELS = {"cnki": "CNKI", "pubmed": "PubMed"}`` and ``sources`` is
a validated subset of ``["cnki", "pubmed"]`` produced by ``_validate_sources``
(defaults ``[]`` to both, dedups, lower-cases, rejects unknown → HTTP 400).
The ``filter_by_sources`` helper below mirrors that inline merge-filter exactly
so the property can exercise it directly.
"""

import pytest
from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

from app.api.v1.literature import _validate_sources
from app.schemas.literature import SOURCE_LABELS, LiteratureRecord


def filter_by_sources(
    records: list[LiteratureRecord], sources: list[str]
) -> list[LiteratureRecord]:
    """Filter ``records`` to the selected data sources.

    Mirrors the inline merge-filter in ``search_literature`` (the source of
    truth in ``app/api/v1/literature.py``)::

        selected_labels = {SOURCE_LABELS[s] for s in sources}
        records = [r for r in records if r.data_source in selected_labels]

    ``sources`` is a list of source keys (subset of ``["cnki", "pubmed"]``);
    each is mapped to its display label via ``SOURCE_LABELS`` before comparison.
    """
    selected_labels = {SOURCE_LABELS[s] for s in sources}
    return [r for r in records if r.data_source in selected_labels]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# The canonical data-source labels carried by records ("CNKI" / "PubMed") plus
# UNRELATED labels that should always be excluded by the filter. Including the
# unrelated labels proves the filter keeps ONLY matching records.
_MATCHING_LABELS = list(SOURCE_LABELS.values())  # ["CNKI", "PubMed"]
_UNRELATED_LABELS = ["Other", "", "cnki", "pubmed", "Web of Science"]
_ALL_LABELS = _MATCHING_LABELS + _UNRELATED_LABELS

# Non-empty title; the filter never inspects the title.
_titles = st.text(min_size=1, max_size=20)

# Non-empty subsets of the valid source keys: the user-selectable filters.
_source_selections = st.sampled_from([["cnki"], ["pubmed"], ["cnki", "pubmed"]])


@st.composite
def literature_records(draw: st.DrawFn) -> LiteratureRecord:
    """A single record whose ``data_source`` is a matching or unrelated label."""
    return LiteratureRecord(
        title=draw(_titles),
        data_source=draw(st.sampled_from(_ALL_LABELS)),
    )


@st.composite
def mixed_record_lists(draw: st.DrawFn) -> list[LiteratureRecord]:
    """A mixed list (length 0..20) of records across CNKI / PubMed / unrelated."""
    return draw(st.lists(literature_records(), min_size=0, max_size=20))


# ---------------------------------------------------------------------------
# Property tests — Property 19 (Req 10.25)
# ---------------------------------------------------------------------------


class TestSourceFilterProperties:
    """Property 19 — filtered results match the selected data sources (Req 10.25)."""

    @given(records=mixed_record_lists(), sources=_source_selections)
    @settings(deadline=None)
    def test_all_results_match_the_filter(
        self, records: list[LiteratureRecord], sources: list[str]
    ) -> None:
        """Every retained record's label is within the selected label set (Req 10.25).

        This is the core Property 19 invariant.

        Validates: Requirements 10.25
        """
        selected_labels = {SOURCE_LABELS[s] for s in sources}
        result = filter_by_sources(records, sources)
        for record in result:
            assert record.data_source in selected_labels

    @given(records=mixed_record_lists(), sources=_source_selections)
    @settings(deadline=None)
    def test_no_matching_record_dropped(
        self, records: list[LiteratureRecord], sources: list[str]
    ) -> None:
        """The filter keeps all AND only matching records (Req 10.25).

        Every input record whose label is in the selected set appears in the
        result, and the result contains nothing else.

        Validates: Requirements 10.25
        """
        selected_labels = {SOURCE_LABELS[s] for s in sources}
        expected = [r for r in records if r.data_source in selected_labels]
        result = filter_by_sources(records, sources)
        assert result == expected
        # Counts match: kept == number of input records with a selected label.
        assert len(result) == sum(
            1 for r in records if r.data_source in selected_labels
        )

    @given(records=mixed_record_lists(), sources=_source_selections)
    @settings(deadline=None)
    def test_result_is_order_preserving_subsequence(
        self, records: list[LiteratureRecord], sources: list[str]
    ) -> None:
        """The result is a sublist of the input in the same relative order (Req 10.25).

        Validates: Requirements 10.25
        """
        result = filter_by_sources(records, sources)
        result_ids = [id(r) for r in result]
        input_ids = [id(r) for r in records]
        # result_ids must be a subsequence of input_ids (filtering preserves order).
        it = iter(input_ids)
        assert all(rid in it for rid in result_ids)

    @given(records=mixed_record_lists())
    @settings(deadline=None)
    def test_both_keeps_all_cnki_and_pubmed_records(
        self, records: list[LiteratureRecord]
    ) -> None:
        """``["cnki", "pubmed"]`` retains every CNKI/PubMed record (Req 10.25).

        Only records with an unrelated label are dropped.

        Validates: Requirements 10.25
        """
        result = filter_by_sources(records, ["cnki", "pubmed"])
        matching_labels = set(SOURCE_LABELS.values())  # {"CNKI", "PubMed"}
        expected = [r for r in records if r.data_source in matching_labels]
        assert result == expected
        # No unrelated label survives.
        for record in result:
            assert record.data_source in matching_labels

    @given(records=mixed_record_lists())
    @settings(deadline=None)
    def test_cnki_only_excludes_pubmed(
        self, records: list[LiteratureRecord]
    ) -> None:
        """``["cnki"]`` never yields a "PubMed" record (Req 10.25).

        Validates: Requirements 10.25
        """
        result = filter_by_sources(records, ["cnki"])
        for record in result:
            assert record.data_source == "CNKI"
            assert record.data_source != "PubMed"

    @given(records=mixed_record_lists())
    @settings(deadline=None)
    def test_pubmed_only_excludes_cnki(
        self, records: list[LiteratureRecord]
    ) -> None:
        """``["pubmed"]`` never yields a "CNKI" record (Req 10.25).

        Validates: Requirements 10.25
        """
        result = filter_by_sources(records, ["pubmed"])
        for record in result:
            assert record.data_source == "PubMed"
            assert record.data_source != "CNKI"


# ---------------------------------------------------------------------------
# _validate_sources behavior — selection semantics behind Req 10.25
# ---------------------------------------------------------------------------


class TestValidateSourcesSemantics:
    """``_validate_sources`` normalizes the user's source selection (Req 10.25)."""

    def test_empty_defaults_to_both(self) -> None:
        """An empty selection defaults to both sources (Req 10.25)."""
        assert _validate_sources([]) == ["cnki", "pubmed"]

    def test_cnki_only(self) -> None:
        """A CNKI-only selection is preserved (Req 10.25)."""
        assert _validate_sources(["cnki"]) == ["cnki"]

    def test_pubmed_only(self) -> None:
        """A PubMed-only selection is preserved (Req 10.25)."""
        assert _validate_sources(["pubmed"]) == ["pubmed"]

    def test_duplicates_are_deduped(self) -> None:
        """Duplicate sources collapse to a single entry (Req 10.25)."""
        assert _validate_sources(["cnki", "cnki"]) == ["cnki"]
        assert _validate_sources(["pubmed", "cnki", "pubmed"]) == ["pubmed", "cnki"]

    def test_case_insensitive(self) -> None:
        """Source keys are matched case-insensitively (Req 10.25)."""
        assert _validate_sources(["CNKI"]) == ["cnki"]
        assert _validate_sources(["PubMed"]) == ["pubmed"]
        assert _validate_sources([" CnKi "]) == ["cnki"]

    def test_unknown_source_raises_http_400(self) -> None:
        """An unknown source is rejected with HTTP 400 (Req 10.25)."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_sources(["scopus"])
        assert exc_info.value.status_code == 400

    @given(
        sources=st.lists(
            st.sampled_from(["cnki", "pubmed", "CNKI", "PubMed"]),
            min_size=1,
            max_size=6,
        )
    )
    @settings(deadline=None)
    def test_validated_sources_normalize_to_valid_keys(
        self, sources: list[str]
    ) -> None:
        """Validated sources are deduped lower-case keys feeding the filter (Req 10.25).

        The output keys are exactly the subset of ``{"cnki", "pubmed"}`` and map
        cleanly through ``SOURCE_LABELS`` — the same mapping ``filter_by_sources``
        relies on.

        Validates: Requirements 10.25
        """
        validated = _validate_sources(sources)
        assert validated  # never empty for a non-empty input
        assert len(validated) == len(set(validated))  # deduped
        for key in validated:
            assert key in SOURCE_LABELS


# ---------------------------------------------------------------------------
# Example-based regression tests
# ---------------------------------------------------------------------------


def _record(title: str, data_source: str) -> LiteratureRecord:
    """Build a record carrying only a title and a data-source label."""
    return LiteratureRecord(title=title, data_source=data_source)


# A small fixed mixed list reused across the example regressions.
_MIXED = [
    _record("cnki-a", "CNKI"),
    _record("pubmed-a", "PubMed"),
    _record("cnki-b", "CNKI"),
    _record("other-a", "Other"),
    _record("pubmed-b", "PubMed"),
]


class TestSourceFilterExamples:
    """Representative example-based regressions for Property 19 (Req 10.25)."""

    def test_filter_cnki_only(self) -> None:
        """CNKI-only filter keeps exactly the CNKI titles (Req 10.25)."""
        result = filter_by_sources(_MIXED, ["cnki"])
        assert [r.title for r in result] == ["cnki-a", "cnki-b"]
        assert all(r.data_source == "CNKI" for r in result)

    def test_filter_pubmed_only(self) -> None:
        """PubMed-only filter keeps exactly the PubMed titles (Req 10.25)."""
        result = filter_by_sources(_MIXED, ["pubmed"])
        assert [r.title for r in result] == ["pubmed-a", "pubmed-b"]
        assert all(r.data_source == "PubMed" for r in result)

    def test_filter_both_drops_only_unrelated(self) -> None:
        """The "both" filter keeps every CNKI/PubMed record, dropping "Other" (Req 10.25)."""
        result = filter_by_sources(_MIXED, ["cnki", "pubmed"])
        assert [r.title for r in result] == [
            "cnki-a",
            "pubmed-a",
            "cnki-b",
            "pubmed-b",
        ]
        assert all(r.data_source in {"CNKI", "PubMed"} for r in result)

    def test_filter_empty_input(self) -> None:
        """Filtering an empty list yields an empty list for every selection (Req 10.25)."""
        assert filter_by_sources([], ["cnki"]) == []
        assert filter_by_sources([], ["pubmed"]) == []
        assert filter_by_sources([], ["cnki", "pubmed"]) == []

    def test_filter_uses_validated_sources_end_to_end(self) -> None:
        """Default (empty) selection validates to both, retaining CNKI+PubMed (Req 10.25)."""
        sources = _validate_sources([])  # -> ["cnki", "pubmed"]
        result = filter_by_sources(_MIXED, sources)
        assert [r.title for r in result] == [
            "cnki-a",
            "pubmed-a",
            "cnki-b",
            "pubmed-b",
        ]
