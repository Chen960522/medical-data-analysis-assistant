"""Report Generation MCP Server package.

Generates structured medical analysis reports (data summary, key findings,
statistical results, visualizations, recommendations) and exports them to
PDF (WeasyPrint) and Word (python-docx), uploading to S3.

The report-content building logic (:mod:`report_generation.builder`) and HTML
rendering (:mod:`report_generation.templates`) are pure and unit-testable; they
do not depend on a running database, S3, or the heavy native export libraries.
The MCP tool wrappers (:mod:`report_generation.server`) are thin layers around
these pure functions, and the export helpers (:mod:`report_generation.exporters`)
import their heavy dependencies lazily.

Requirements: 5.1-5.7
"""

from .models import (
    DEFAULT_SECTIONS,
    SECTION_TITLES,
    ChartReference,
    DataSourceMetadata,
    ReportContent,
    ReportSection,
)
from .builder import build_report_content

__all__ = [
    "DEFAULT_SECTIONS",
    "SECTION_TITLES",
    "ChartReference",
    "DataSourceMetadata",
    "ReportContent",
    "ReportSection",
    "build_report_content",
]
