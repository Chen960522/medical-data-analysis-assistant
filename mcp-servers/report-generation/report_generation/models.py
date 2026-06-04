"""Data models for structured medical analysis reports.

Defines the dataclasses that make up an :class:`ReportContent` along with the
canonical medical report section order and human-readable section titles.

Requirements: 5.1, 5.2, 5.4, 5.7
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Canonical medical report section order (Requirement 5.2).
# The five required sections: data summary, key findings, statistical analysis
# results, visualizations, and recommendations.
DEFAULT_SECTIONS: list[str] = [
    "data_summary",
    "key_findings",
    "statistical_results",
    "visualizations",
    "recommendations",
]

# Human-readable (clinical professional friendly) titles for each section.
# Bilingual labels keep the report readable for medical staff while keeping a
# stable English key for programmatic access.
SECTION_TITLES: dict[str, str] = {
    "data_summary": "数据摘要 (Data Summary)",
    "key_findings": "关键发现 (Key Findings)",
    "statistical_results": "统计分析结果 (Statistical Analysis Results)",
    "visualizations": "可视化图表 (Visualizations)",
    "recommendations": "建议 (Recommendations)",
}


@dataclass
class ChartReference:
    """An inline reference to a chart embedded within the report.

    Charts are referenced inline within the visualizations section
    (Requirement 5.4). ``image_data_uri`` may carry a rendered PNG/SVG as a
    data URI for embedding into exported documents; when absent, exporters fall
    back to rendering a textual placeholder using ``title``/``caption``.
    """

    chart_id: str
    title: str
    chart_type: str = ""
    caption: str = ""
    image_data_uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportSection:
    """A single section of the report.

    ``key`` is the stable section identifier (one of :data:`DEFAULT_SECTIONS`),
    ``title`` is the human-readable heading, ``body`` is the section prose, and
    ``charts`` holds any inline chart references that belong to the section.
    """

    key: str
    title: str
    body: str = ""
    charts: list[ChartReference] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "body": self.body,
            "charts": [c.to_dict() for c in self.charts],
        }


@dataclass
class DataSourceMetadata:
    """Metadata about the analyzed data source (Requirement 5.7).

    Includes file name, upload time, row count, and column count.
    """

    file_name: str = ""
    upload_time: str = ""
    row_count: int = 0
    column_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReportContent:
    """The full structured report content.

    A report always carries a title, data source metadata, and the ordered list
    of sections. The five required sections are guaranteed to be present by the
    builder regardless of caller input.
    """

    title: str
    metadata: DataSourceMetadata
    sections: list[ReportSection] = field(default_factory=list)
    analysis_id: str = ""

    def section_keys(self) -> list[str]:
        """Return the ordered list of section keys present in the report."""
        return [s.key for s in self.sections]

    def get_section(self, key: str) -> ReportSection | None:
        """Return the section with the given key, or ``None`` if absent."""
        for section in self.sections:
            if section.key == key:
                return section
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report content to a JSON-compatible dictionary."""
        return {
            "title": self.title,
            "analysis_id": self.analysis_id,
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
        }
