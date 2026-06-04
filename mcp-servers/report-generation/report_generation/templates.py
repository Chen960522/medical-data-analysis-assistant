"""Jinja2 HTML templating for medical analysis reports.

Renders a :class:`~report_generation.models.ReportContent` into a clean, print
friendly HTML document used by WeasyPrint for PDF export. Charts referenced
inline are embedded as ``<img>`` tags when an image data URI is available, or as
a labelled placeholder otherwise (Requirement 5.4).

Only Jinja2 is required here (no native libraries), so HTML rendering is fully
unit-testable.

Requirements: 5.2, 5.3, 5.4, 5.7
"""

from __future__ import annotations

from jinja2 import Environment, select_autoescape

from .models import ReportContent

# A clean medical report layout: title block, data-source metadata header, and
# the standard ordered sections. Section bodies are rendered with simple
# paragraph/bullet handling. ``include_charts`` toggles inline chart embedding.
_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8" />
<title>{{ report.title }}</title>
<style>
  @page { size: A4; margin: 2cm; }
  body { font-family: "Helvetica Neue", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
         color: #1f2933; line-height: 1.6; font-size: 12pt; }
  h1.report-title { color: #0b5394; font-size: 22pt; margin-bottom: 4px; border-bottom: 3px solid #0b5394;
                    padding-bottom: 8px; }
  .metadata { background: #f0f5fa; border: 1px solid #d4e2f0; border-radius: 6px;
              padding: 12px 16px; margin: 16px 0 24px; font-size: 10.5pt; }
  .metadata table { width: 100%; border-collapse: collapse; }
  .metadata td { padding: 2px 8px; }
  .metadata td.label { color: #52606d; width: 40%; }
  .metadata td.value { color: #1f2933; font-weight: 600; }
  h2.section-title { color: #0b5394; font-size: 15pt; margin-top: 28px;
                     border-left: 4px solid #0b5394; padding-left: 10px; }
  .section-body p { margin: 8px 0; }
  .section-body ul { margin: 8px 0 8px 18px; }
  .chart { margin: 16px 0; page-break-inside: avoid; text-align: center; }
  .chart img { max-width: 100%; height: auto; border: 1px solid #d4e2f0; border-radius: 4px; }
  .chart .placeholder { border: 1px dashed #9aa5b1; border-radius: 4px; padding: 24px;
                        color: #52606d; background: #fafbfc; }
  .chart .caption { font-size: 10pt; color: #52606d; margin-top: 6px; }
</style>
</head>
<body>
  <h1 class="report-title">{{ report.title }}</h1>

  <div class="metadata">
    <table>
      <tr><td class="label">数据文件 (File Name)</td><td class="value">{{ meta.file_name or "未提供" }}</td></tr>
      <tr><td class="label">上传时间 (Upload Time)</td><td class="value">{{ meta.upload_time or "未提供" }}</td></tr>
      <tr><td class="label">数据行数 (Row Count)</td><td class="value">{{ meta.row_count }}</td></tr>
      <tr><td class="label">数据列数 (Column Count)</td><td class="value">{{ meta.column_count }}</td></tr>
    </table>
  </div>

  {% for section in report.sections %}
  <section>
    <h2 class="section-title">{{ section.title }}</h2>
    <div class="section-body">{{ render_body(section.body) }}</div>
    {% if include_charts %}
      {% for chart in section.charts %}
      <div class="chart">
        {% if chart.image_data_uri %}
          <img src="{{ chart.image_data_uri }}" alt="{{ chart.title }}" />
        {% else %}
          <div class="placeholder">[图表: {{ chart.title }}{% if chart.chart_type %} ({{ chart.chart_type }}){% endif %}]</div>
        {% endif %}
        <div class="caption">{{ chart.title }}{% if chart.caption %} — {{ chart.caption }}{% endif %}</div>
      </div>
      {% endfor %}
    {% endif %}
  </section>
  {% endfor %}
</body>
</html>
"""


def _render_body(body: str) -> str:
    """Render a section body string to safe HTML.

    Lines beginning with ``-`` or ``*`` become list items; blank lines separate
    paragraphs. The Jinja environment has autoescaping enabled, so we escape
    each text fragment before wrapping it in structural tags.
    """
    from markupsafe import Markup, escape

    if not body:
        return Markup("")

    html_parts: list[str] = []
    bullet_buffer: list[str] = []

    def flush_bullets() -> None:
        if bullet_buffer:
            items = "".join(f"<li>{escape(item)}</li>" for item in bullet_buffer)
            html_parts.append(f"<ul>{items}</ul>")
            bullet_buffer.clear()

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            flush_bullets()
            continue
        if line.startswith(("- ", "* ")):
            bullet_buffer.append(line[2:].strip())
        else:
            flush_bullets()
            html_parts.append(f"<p>{escape(line)}</p>")

    flush_bullets()
    return Markup("".join(html_parts))


def _build_environment() -> Environment:
    """Create the Jinja2 environment with autoescaping for HTML."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    env.globals["render_body"] = _render_body
    return env


def render_html(report: ReportContent, include_charts: bool = True) -> str:
    """Render :class:`ReportContent` to a complete HTML document string.

    Args:
        report: The structured report content.
        include_charts: Whether to embed inline chart references (Requirement 5.4).

    Returns:
        A full HTML document as a string, suitable for WeasyPrint.
    """
    env = _build_environment()
    template = env.from_string(_REPORT_TEMPLATE)
    return template.render(report=report, meta=report.metadata, include_charts=include_charts)
