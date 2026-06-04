"""Tests for Jinja2 HTML rendering of report content.

HTML rendering only depends on Jinja2 (no native libraries), so it is fully
unit-testable. These tests verify the rendered document contains the report
title, the data-source metadata header (Requirement 5.7), every section title,
and inline chart embedding (Requirement 5.4).
"""

from __future__ import annotations

import pytest

from report_generation import build_report_content
from report_generation.models import DEFAULT_SECTIONS, SECTION_TITLES

# Skip the whole module if jinja2 is not installed in the environment.
pytest.importorskip("jinja2")

from report_generation.templates import render_html  # noqa: E402  (after importorskip)


def _sample_report():
    data = {
        "analysis_id": "r-1",
        "title": "实验室指标分析报告",
        "metadata": {
            "file_name": "labs.csv",
            "upload_time": "2024-03-03T08:00:00Z",
            "row_count": 320,
            "column_count": 12,
        },
        "results": [
            {"result_type": "key_findings", "result_data": {"items": ["指标 A 偏高", "指标 B 正常"]}},
            {"result_type": "descriptive_statistics", "result_data": {"text": "均值 5.4，标准差 1.2"}},
        ],
        "charts": [
            {
                "chart_id": "c1",
                "title": "指标分布直方图",
                "chart_type": "histogram",
                "caption": "指标 A 分布",
                "image_data_uri": "data:image/png;base64,AAAA",
            },
            {"chart_id": "c2", "title": "趋势折线图", "chart_type": "line"},
        ],
    }
    return build_report_content(data)


def test_html_contains_report_title() -> None:
    html = render_html(_sample_report())
    assert "实验室指标分析报告" in html
    assert "<!DOCTYPE html>" in html


def test_html_contains_all_section_titles() -> None:
    html = render_html(_sample_report())
    for key in DEFAULT_SECTIONS:
        assert SECTION_TITLES[key] in html, f"missing section title for {key}"


def test_html_contains_metadata_header() -> None:
    html = render_html(_sample_report())
    # Metadata values rendered in the header table (Requirement 5.7).
    assert "labs.csv" in html
    assert "2024-03-03T08:00:00Z" in html
    assert "320" in html
    assert "12" in html


def test_html_embeds_chart_image_when_data_uri_present() -> None:
    html = render_html(_sample_report(), include_charts=True)
    # Chart with image data URI is embedded as an <img> tag (Requirement 5.4).
    assert "data:image/png;base64,AAAA" in html
    assert "<img" in html


def test_html_renders_placeholder_for_chart_without_image() -> None:
    html = render_html(_sample_report(), include_charts=True)
    # The second chart (no image) renders a labelled placeholder.
    assert "趋势折线图" in html
    assert "placeholder" in html


def test_html_omits_charts_when_include_charts_false() -> None:
    html = render_html(_sample_report(), include_charts=False)
    assert "data:image/png;base64,AAAA" not in html
    assert "<img" not in html


def test_html_renders_bullet_items_as_list() -> None:
    html = render_html(_sample_report())
    assert "<ul>" in html
    assert "<li>" in html
    assert "指标 A 偏高" in html


def test_html_escapes_special_characters() -> None:
    data = {
        "title": "A & B <script>",
        "metadata": {"file_name": "x<y>.csv"},
        "results": [{"result_type": "key_findings", "result_data": "危险 <tag> & 符号"}],
    }
    html = render_html(build_report_content(data))
    # Autoescaping prevents raw HTML injection from data content.
    assert "<script>" not in html
    assert "&lt;script&gt;" in html or "&amp;" in html


def test_html_renders_with_empty_data() -> None:
    html = render_html(build_report_content({}))
    # Even with no data, all section titles and the metadata header render.
    for key in DEFAULT_SECTIONS:
        assert SECTION_TITLES[key] in html
    assert "未提供" in html  # placeholder for missing file name / upload time
