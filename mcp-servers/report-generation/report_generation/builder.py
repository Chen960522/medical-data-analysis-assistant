"""Pure functions that build structured report content from analysis results.

These functions take plain analysis data (dictionaries, as would be loaded from
the database or returned by the analysis Agent) and produce a
:class:`~report_generation.models.ReportContent`. They have no dependency on a
database, S3, or the heavy export libraries, which makes them fully unit-testable.

Key invariant (Requirement 5.2 / Property 12): the produced report ALWAYS
contains the five required sections — data summary, key findings, statistical
analysis results, visualizations, and recommendations — even when given partial
or empty analysis data, and even when a custom ``sections`` subset is requested.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.7
"""

from __future__ import annotations

from typing import Any

from .models import (
    DEFAULT_SECTIONS,
    SECTION_TITLES,
    ChartReference,
    DataSourceMetadata,
    ReportContent,
    ReportSection,
)

# Sections that must always appear in a generated report (Requirement 5.2).
REQUIRED_SECTIONS: tuple[str, ...] = tuple(DEFAULT_SECTIONS)


def build_report_content(
    analysis_data: dict[str, Any] | None,
    sections: list[str] | None = None,
) -> ReportContent:
    """Build a structured :class:`ReportContent` from analysis data.

    Args:
        analysis_data: Mapping describing the analysis. Recognized keys:
            ``analysis_id``, ``title``, ``metadata`` / data-source fields
            (``file_name``, ``upload_time``, ``row_count``, ``column_count``),
            ``results`` (list of ``{"result_type", "result_data"}``), and
            ``charts`` (list of chart descriptors). All keys are optional;
            missing data degrades gracefully to placeholder prose.
        sections: Optional subset/ordering of section keys to include. The five
            required sections are always present regardless of this argument;
            any extra recognized keys are honored in the requested order.

    Returns:
        A fully populated :class:`ReportContent`. The five required sections are
        guaranteed to be present (Requirement 5.2).
    """
    data = analysis_data or {}

    metadata = _build_metadata(data)
    title = _resolve_title(data, metadata)
    chart_refs = _build_chart_references(data)
    results = _normalize_results(data.get("results"))

    ordered_keys = _resolve_section_order(sections)

    section_objs: list[ReportSection] = []
    for key in ordered_keys:
        section_objs.append(_build_section(key, data, metadata, results, chart_refs))

    return ReportContent(
        title=title,
        metadata=metadata,
        sections=section_objs,
        analysis_id=str(data.get("analysis_id", "")),
    )


# --- Section ordering ---


def _resolve_section_order(sections: list[str] | None) -> list[str]:
    """Resolve the final ordered section keys.

    Guarantees all required sections are present. When a custom subset is given,
    its recognized entries are placed first (in requested order, deduplicated),
    then any missing required sections are appended in canonical order.
    """
    if not sections:
        return list(DEFAULT_SECTIONS)

    ordered: list[str] = []
    for key in sections:
        if key in SECTION_TITLES and key not in ordered:
            ordered.append(key)

    # Append any required sections that were not requested, preserving canonical order.
    for key in DEFAULT_SECTIONS:
        if key not in ordered:
            ordered.append(key)

    return ordered


# --- Metadata & title ---


def _build_metadata(data: dict[str, Any]) -> DataSourceMetadata:
    """Extract data-source metadata (Requirement 5.7).

    Accepts either a nested ``metadata`` mapping or top-level fields, and
    tolerates a few common key aliases.
    """
    meta = data.get("metadata")
    source: dict[str, Any] = meta if isinstance(meta, dict) else data

    return DataSourceMetadata(
        file_name=str(_first(source, "file_name", "filename", "name", default="") or ""),
        upload_time=str(_first(source, "upload_time", "uploaded_at", "created_at", default="") or ""),
        row_count=_as_int(_first(source, "row_count", "rows", "total_rows", default=0)),
        column_count=_as_int(_first(source, "column_count", "columns", "total_columns", default=0)),
    )


def _resolve_title(data: dict[str, Any], metadata: DataSourceMetadata) -> str:
    """Resolve a report title, falling back to a sensible default."""
    title = data.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    if metadata.file_name:
        return f"医学数据分析报告 - {metadata.file_name}"
    return "医学数据分析报告 (Medical Data Analysis Report)"


# --- Chart references (Requirement 5.4) ---


def _build_chart_references(data: dict[str, Any]) -> list[ChartReference]:
    """Normalize chart descriptors into :class:`ChartReference` objects."""
    raw = data.get("charts")
    if not isinstance(raw, list):
        return []

    refs: list[ChartReference] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        chart_id = str(_first(item, "chart_id", "id", default=f"chart_{idx + 1}"))
        title = str(_first(item, "title", "name", default=f"图表 {idx + 1}"))
        chart_type = str(_first(item, "chart_type", "type", default=""))
        caption = str(_first(item, "caption", "description", default=""))
        image = _first(item, "image_data_uri", "image", "data_uri", default=None)
        refs.append(
            ChartReference(
                chart_id=chart_id,
                title=title,
                chart_type=chart_type,
                caption=caption,
                image_data_uri=str(image) if isinstance(image, str) and image else None,
            )
        )
    return refs


# --- Section builders ---


def _build_section(
    key: str,
    data: dict[str, Any],
    metadata: DataSourceMetadata,
    results: list[dict[str, Any]],
    chart_refs: list[ChartReference],
) -> ReportSection:
    """Build a single report section by key."""
    title = SECTION_TITLES.get(key, key.replace("_", " ").title())

    if key == "data_summary":
        body = _build_data_summary(data, metadata, results)
        return ReportSection(key=key, title=title, body=body)

    if key == "key_findings":
        body = _build_key_findings(results)
        return ReportSection(key=key, title=title, body=body)

    if key == "statistical_results":
        body = _build_statistical_results(results)
        return ReportSection(key=key, title=title, body=body)

    if key == "visualizations":
        body = _build_visualizations_body(chart_refs)
        return ReportSection(key=key, title=title, body=body, charts=list(chart_refs))

    if key == "recommendations":
        body = _build_recommendations(data, results)
        return ReportSection(key=key, title=title, body=body)

    # Unknown but explicitly requested section: render any provided custom text.
    custom = data.get("custom_sections", {})
    body = str(custom.get(key, "")) if isinstance(custom, dict) else ""
    return ReportSection(key=key, title=title, body=body)


def _build_data_summary(
    data: dict[str, Any],
    metadata: DataSourceMetadata,
    results: list[dict[str, Any]],
) -> str:
    """Build the data summary section, embedding data-source metadata (5.7)."""
    lines: list[str] = []
    file_name = metadata.file_name or "未提供"
    upload_time = metadata.upload_time or "未提供"
    lines.append(
        f"本报告基于数据文件「{file_name}」的分析结果生成。"
        f"该数据集共包含 {metadata.row_count} 行记录、{metadata.column_count} 个字段，"
        f"上传时间为 {upload_time}。"
    )

    summary = _find_result(results, "data_summary", "summary", "overview")
    if summary:
        text = _result_text(summary)
        if text:
            lines.append(text)

    if len(lines) == 1:
        lines.append("本节概述了数据来源及规模，作为后续分析的基础。")
    return "\n\n".join(lines)


def _build_key_findings(results: list[dict[str, Any]]) -> str:
    """Build key findings in clear, non-technical language (Requirement 5.3)."""
    findings = _find_result(results, "key_findings", "findings", "insights")
    if findings:
        items = _result_items(findings)
        if items:
            return "\n".join(f"- {item}" for item in items)
        text = _result_text(findings)
        if text:
            return text

    # Derive plain-language findings from other available results.
    derived: list[str] = []
    for result in results:
        rtype = str(result.get("result_type", ""))
        text = _result_text(result)
        if not text:
            continue
        label = _RESULT_TYPE_LABELS.get(rtype, rtype.replace("_", " "))
        derived.append(f"在「{label}」方面：{text}")

    if derived:
        return "\n".join(f"- {item}" for item in derived)
    return "本次分析尚未生成可供临床解读的关键发现，建议补充更多数据或分析维度。"


def _build_statistical_results(results: list[dict[str, Any]]) -> str:
    """Build the statistical analysis results section."""
    stat_types = (
        "descriptive_statistics",
        "descriptive",
        "statistics",
        "correlation",
        "correlations",
        "outliers",
        "trend",
        "trends",
        "group_comparison",
        "grouping",
    )
    blocks: list[str] = []
    for result in results:
        rtype = str(result.get("result_type", ""))
        if rtype in stat_types:
            label = _RESULT_TYPE_LABELS.get(rtype, rtype.replace("_", " "))
            text = _result_text(result)
            if text:
                blocks.append(f"**{label}**：{text}")

    if blocks:
        return "\n\n".join(blocks)
    return "暂无可用的统计分析结果。"


def _build_visualizations_body(chart_refs: list[ChartReference]) -> str:
    """Build the visualizations narrative; charts are attached inline (5.4)."""
    if not chart_refs:
        return "本报告暂无关联的可视化图表。"
    lines = [f"本节包含 {len(chart_refs)} 个可视化图表，已内嵌于报告中："]
    for idx, ref in enumerate(chart_refs, start=1):
        descriptor = ref.title
        if ref.chart_type:
            descriptor += f"（{ref.chart_type}）"
        lines.append(f"{idx}. {descriptor}")
    return "\n".join(lines)


def _build_recommendations(data: dict[str, Any], results: list[dict[str, Any]]) -> str:
    """Build the recommendations section."""
    recs = _find_result(results, "recommendations", "suggestions", "advice")
    if recs:
        items = _result_items(recs)
        if items:
            return "\n".join(f"- {item}" for item in items)
        text = _result_text(recs)
        if text:
            return text

    top_level = data.get("recommendations")
    if isinstance(top_level, list) and top_level:
        return "\n".join(f"- {str(item)}" for item in top_level)
    if isinstance(top_level, str) and top_level.strip():
        return top_level.strip()

    return "建议结合临床背景对上述发现进行进一步验证，并在必要时扩充样本量或补充分析维度。"


# --- Helpers ---

_RESULT_TYPE_LABELS: dict[str, str] = {
    "descriptive_statistics": "描述性统计",
    "descriptive": "描述性统计",
    "statistics": "统计指标",
    "correlation": "相关性分析",
    "correlations": "相关性分析",
    "outliers": "异常值检测",
    "trend": "趋势分析",
    "trends": "趋势分析",
    "group_comparison": "分组比较",
    "grouping": "分组比较",
    "data_summary": "数据摘要",
    "key_findings": "关键发现",
}


def _normalize_results(raw: Any) -> list[dict[str, Any]]:
    """Coerce the results payload into a list of dicts."""
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        # Mapping of result_type -> result_data.
        return [{"result_type": k, "result_data": v} for k, v in raw.items()]
    return []


def _find_result(results: list[dict[str, Any]], *types: str) -> dict[str, Any] | None:
    """Return the first result whose result_type matches one of ``types``."""
    wanted = set(types)
    for result in results:
        if str(result.get("result_type", "")) in wanted:
            return result
    return None


def _result_text(result: dict[str, Any]) -> str:
    """Extract a human-readable text representation from a result."""
    payload = result.get("result_data", result)
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for candidate_key in ("text", "summary", "description", "narrative"):
            value = payload.get(candidate_key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        # Fall back to a compact key: value rendering of scalar fields.
        parts = [
            f"{k}={v}"
            for k, v in payload.items()
            if isinstance(v, (str, int, float, bool))
        ]
        if parts:
            return "；".join(parts)
    if isinstance(payload, list):
        items = [str(x) for x in payload if isinstance(x, (str, int, float, bool))]
        if items:
            return "；".join(items)
    return ""


def _result_items(result: dict[str, Any]) -> list[str]:
    """Extract a list of bullet items from a result, if present."""
    payload = result.get("result_data", result)
    if isinstance(payload, list):
        return [str(x).strip() for x in payload if str(x).strip()]
    if isinstance(payload, dict):
        for candidate_key in ("items", "findings", "points", "list"):
            value = payload.get(candidate_key)
            if isinstance(value, list):
                return [str(x).strip() for x in value if str(x).strip()]
    return []


def _first(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``keys`` in ``source``."""
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _as_int(value: Any) -> int:
    """Best-effort conversion to a non-negative int."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result >= 0 else 0
