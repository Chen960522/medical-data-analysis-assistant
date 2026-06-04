"""Unit and property tests for pure report-content building.

These tests exercise :func:`report_generation.builder.build_report_content`,
which is the core invariant-bearing logic (Requirement 5.2 / Property 12): a
generated report ALWAYS contains the five required sections, carries data source
metadata (Requirement 5.7), and embeds chart references inline within the
visualizations section (Requirement 5.4).

No native libraries are required for these tests.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from report_generation import build_report_content
from report_generation.models import DEFAULT_SECTIONS, SECTION_TITLES, ReportContent


# --- Fixtures / sample data ------------------------------------------------


def _full_analysis_data() -> dict:
    """A representative, fully populated analysis payload."""
    return {
        "analysis_id": "a-123",
        "title": "临床试验数据分析",
        "metadata": {
            "file_name": "trial_results.csv",
            "upload_time": "2024-05-01T10:00:00Z",
            "row_count": 1200,
            "column_count": 18,
        },
        "results": [
            {"result_type": "data_summary", "result_data": {"text": "数据集覆盖 2 个治疗组。"}},
            {
                "result_type": "key_findings",
                "result_data": {"items": ["治疗组 A 的有效率更高", "未观察到严重不良事件"]},
            },
            {"result_type": "descriptive_statistics", "result_data": {"mean": 12.3, "std": 2.1}},
            {"result_type": "correlation", "result_data": {"text": "剂量与疗效正相关 (r=0.62)。"}},
            {"result_type": "recommendations", "result_data": {"items": ["建议扩大样本量复核结论"]}},
        ],
        "charts": [
            {
                "chart_id": "c1",
                "title": "疗效对比柱状图",
                "chart_type": "bar",
                "caption": "两组有效率对比",
                "image_data_uri": "data:image/png;base64,AAAA",
            },
            {"chart_id": "c2", "title": "剂量-疗效散点图", "chart_type": "scatter"},
        ],
    }


# --- Required-section completeness (Requirement 5.2 / Property 12) ----------


def test_full_data_yields_all_five_required_sections() -> None:
    report = build_report_content(_full_analysis_data())
    keys = report.section_keys()
    for required in DEFAULT_SECTIONS:
        assert required in keys, f"missing required section: {required}"


def test_empty_data_yields_all_five_required_sections() -> None:
    report = build_report_content({})
    assert report.section_keys() == DEFAULT_SECTIONS


def test_none_data_yields_all_five_required_sections() -> None:
    report = build_report_content(None)
    assert set(report.section_keys()) == set(DEFAULT_SECTIONS)
    # Every section still has a non-empty body (graceful placeholder prose).
    for section in report.sections:
        assert section.body.strip() != ""


def test_partial_data_still_yields_all_required_sections() -> None:
    partial = {
        "analysis_id": "p-1",
        "metadata": {"file_name": "partial.csv", "row_count": 10},
        "results": [{"result_type": "key_findings", "result_data": "仅有部分发现。"}],
    }
    report = build_report_content(partial)
    for required in DEFAULT_SECTIONS:
        assert required in report.section_keys()


def test_custom_subset_still_includes_all_required_sections() -> None:
    # Request only a single section; the builder must still include all five.
    report = build_report_content(_full_analysis_data(), sections=["recommendations"])
    keys = report.section_keys()
    assert keys[0] == "recommendations", "requested section should come first"
    for required in DEFAULT_SECTIONS:
        assert required in keys


def test_custom_subset_ordering_is_honored_then_required_appended() -> None:
    report = build_report_content(
        _full_analysis_data(),
        sections=["visualizations", "key_findings"],
    )
    keys = report.section_keys()
    assert keys[:2] == ["visualizations", "key_findings"]
    # Remaining required sections appended in canonical order.
    assert set(keys) == set(DEFAULT_SECTIONS)


def test_unknown_requested_sections_are_ignored_but_required_kept() -> None:
    report = build_report_content(_full_analysis_data(), sections=["nonexistent", "data_summary"])
    keys = report.section_keys()
    assert "nonexistent" not in keys
    for required in DEFAULT_SECTIONS:
        assert required in keys


# --- Data source metadata (Requirement 5.7) --------------------------------


def test_metadata_present_from_nested_metadata_mapping() -> None:
    report = build_report_content(_full_analysis_data())
    meta = report.metadata
    assert meta.file_name == "trial_results.csv"
    assert meta.upload_time == "2024-05-01T10:00:00Z"
    assert meta.row_count == 1200
    assert meta.column_count == 18


def test_metadata_present_from_top_level_fields() -> None:
    data = {
        "analysis_id": "x",
        "file_name": "labs.xlsx",
        "upload_time": "2024-01-01",
        "row_count": 50,
        "column_count": 7,
    }
    report = build_report_content(data)
    meta = report.metadata
    assert meta.file_name == "labs.xlsx"
    assert meta.upload_time == "2024-01-01"
    assert meta.row_count == 50
    assert meta.column_count == 7


def test_metadata_key_aliases_are_supported() -> None:
    data = {"filename": "aliased.json", "uploaded_at": "2024-02-02", "rows": 9, "columns": 3}
    report = build_report_content(data)
    meta = report.metadata
    assert meta.file_name == "aliased.json"
    assert meta.upload_time == "2024-02-02"
    assert meta.row_count == 9
    assert meta.column_count == 3


def test_metadata_embedded_in_data_summary_body() -> None:
    report = build_report_content(_full_analysis_data())
    summary = report.get_section("data_summary")
    assert summary is not None
    # Row/column counts and file name appear in the prose (Requirement 5.7).
    assert "trial_results.csv" in summary.body
    assert "1200" in summary.body
    assert "18" in summary.body


def test_metadata_counts_default_to_zero_and_are_non_negative() -> None:
    report = build_report_content({"metadata": {"row_count": "not-a-number", "column_count": -5}})
    assert report.metadata.row_count == 0
    assert report.metadata.column_count == 0


# --- Inline chart references in visualizations (Requirement 5.4) ------------


def test_chart_references_inline_in_visualizations_section() -> None:
    report = build_report_content(_full_analysis_data())
    viz = report.get_section("visualizations")
    assert viz is not None
    assert len(viz.charts) == 2
    chart_ids = {c.chart_id for c in viz.charts}
    assert chart_ids == {"c1", "c2"}
    # First chart carries an embeddable image data URI.
    first = next(c for c in viz.charts if c.chart_id == "c1")
    assert first.image_data_uri == "data:image/png;base64,AAAA"
    assert first.chart_type == "bar"


def test_charts_only_attached_to_visualizations_section() -> None:
    report = build_report_content(_full_analysis_data())
    for section in report.sections:
        if section.key != "visualizations":
            assert section.charts == [], f"{section.key} should not carry charts"


def test_visualizations_body_mentions_chart_count_when_present() -> None:
    report = build_report_content(_full_analysis_data())
    viz = report.get_section("visualizations")
    assert viz is not None
    assert "2" in viz.body


def test_no_charts_yields_empty_chart_list_but_section_present() -> None:
    report = build_report_content({"metadata": {"file_name": "x.csv"}})
    viz = report.get_section("visualizations")
    assert viz is not None
    assert viz.charts == []
    assert viz.body.strip() != ""


# --- Key findings & recommendations rendering ------------------------------


def test_key_findings_rendered_as_bullets() -> None:
    report = build_report_content(_full_analysis_data())
    findings = report.get_section("key_findings")
    assert findings is not None
    assert "- 治疗组 A 的有效率更高" in findings.body
    assert "- 未观察到严重不良事件" in findings.body


def test_recommendations_rendered_as_bullets() -> None:
    report = build_report_content(_full_analysis_data())
    recs = report.get_section("recommendations")
    assert recs is not None
    assert "建议扩大样本量复核结论" in recs.body


def test_serialization_round_trips_to_dict() -> None:
    report = build_report_content(_full_analysis_data())
    payload = report.to_dict()
    assert payload["title"]
    assert payload["metadata"]["file_name"] == "trial_results.csv"
    assert len(payload["sections"]) == len(DEFAULT_SECTIONS)
    # Visualizations section serializes its inline charts.
    viz = next(s for s in payload["sections"] if s["key"] == "visualizations")
    assert len(viz["charts"]) == 2


# --- Property-based invariants (Property 12 family) ------------------------

# Strategy for arbitrary, possibly-partial analysis payloads.
_metadata_strategy = st.fixed_dictionaries(
    {},
    optional={
        "file_name": st.text(max_size=30),
        "upload_time": st.text(max_size=30),
        "row_count": st.integers(min_value=-100, max_value=10_000),
        "column_count": st.integers(min_value=-100, max_value=1000),
    },
)

_result_strategy = st.fixed_dictionaries(
    {
        "result_type": st.sampled_from(
            ["data_summary", "key_findings", "descriptive_statistics", "correlation", "recommendations", "unknown"]
        ),
        "result_data": st.one_of(
            st.text(max_size=40),
            st.lists(st.text(max_size=20), max_size=4),
            st.dictionaries(st.text(min_size=1, max_size=8), st.integers(), max_size=4),
        ),
    }
)

_chart_strategy = st.fixed_dictionaries(
    {"title": st.text(max_size=20)},
    optional={
        "chart_id": st.text(min_size=1, max_size=10),
        "chart_type": st.sampled_from(["bar", "line", "scatter", "pie"]),
        "image_data_uri": st.just("data:image/png;base64,AAAA"),
    },
)

_analysis_strategy = st.fixed_dictionaries(
    {},
    optional={
        "analysis_id": st.text(max_size=12),
        "title": st.text(max_size=30),
        "metadata": _metadata_strategy,
        "results": st.lists(_result_strategy, max_size=6),
        "charts": st.lists(_chart_strategy, max_size=5),
    },
)


@given(_analysis_strategy)
def test_property_report_always_has_all_required_sections(data: dict) -> None:
    """Property 12: any analysis data yields all five required sections.

    **Validates: Requirements 5.1, 5.2**
    """
    report = build_report_content(data)
    keys = set(report.section_keys())
    for required in DEFAULT_SECTIONS:
        assert required in keys


@given(_analysis_strategy)
def test_property_metadata_always_present(data: dict) -> None:
    """Every report carries data source metadata of the right types (5.7)."""
    report = build_report_content(data)
    assert isinstance(report.metadata.file_name, str)
    assert isinstance(report.metadata.upload_time, str)
    assert isinstance(report.metadata.row_count, int) and report.metadata.row_count >= 0
    assert isinstance(report.metadata.column_count, int) and report.metadata.column_count >= 0


@given(
    _analysis_strategy,
    st.lists(st.sampled_from(DEFAULT_SECTIONS + ["unknown_section"]), max_size=6),
)
def test_property_custom_subset_preserves_required_sections(data: dict, subset: list[str]) -> None:
    """Requesting any subset never drops a required section (5.2)."""
    report = build_report_content(data, sections=subset)
    keys = set(report.section_keys())
    for required in DEFAULT_SECTIONS:
        assert required in keys


@given(_analysis_strategy)
def test_property_charts_only_in_visualizations(data: dict) -> None:
    """Inline chart references appear only in the visualizations section (5.4)."""
    report = build_report_content(data)
    for section in report.sections:
        if section.key != "visualizations":
            assert section.charts == []


@given(_analysis_strategy)
def test_property_every_section_has_a_known_title(data: dict) -> None:
    """Each required section uses its canonical human-readable title."""
    report = build_report_content(data)
    for section in report.sections:
        if section.key in DEFAULT_SECTIONS:
            assert section.title == SECTION_TITLES[section.key]


def test_returns_report_content_instance() -> None:
    assert isinstance(build_report_content({}), ReportContent)
