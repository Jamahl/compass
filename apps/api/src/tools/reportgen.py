"""Report generation: markdown -> HTML -> PDF via fpdf2.

Sync function; the writer/orchestrator runs it off the event loop in a
thread. Uses `markdown` (tables + fenced code) for rendering and fpdf2's
`write_html` for pure-Python PDF output (no system deps like cairo/pango).
Files are written under the canonical artifacts directory from
`src.store.artifacts_dir`.
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown
from fpdf import FPDF

from src.store.artifacts_dir import get_artifact_path


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _sanitize_for_fpdf(html: str) -> str:
    """fpdf2's write_html supports a subset of HTML. Strip constructs that
    either break or are unsupported so rendering is resilient.
    """
    # Strip <code> inline tags — keep their content
    html = re.sub(r"</?code>", "", html)
    # Strip <pre> tags — keep inner content in a paragraph
    html = re.sub(r"<pre>", "<p>", html)
    html = re.sub(r"</pre>", "</p>", html)
    # hr renders weirdly — replace with spacing paragraph
    html = re.sub(r"<hr\s*/?>", "<p>&nbsp;</p>", html)
    return html


def generate_report_pdf(
    run_id: str,
    artifact_id: str,
    content_md: str,
    title: str,
) -> Path:
    """Render `content_md` to a styled PDF; return the written file path.

    - Converts markdown with `tables` and `fenced_code` extensions.
    - Feeds through fpdf2's write_html (letter page, 1in margins).
    - Writes to artifacts dir as `{run_id}/{artifact_id}.pdf`.
    """
    body_html = markdown.markdown(
        content_md,
        extensions=["tables", "fenced_code"],
        output_format="html5",
    )
    body_html = _sanitize_for_fpdf(body_html)
    safe_title = _html_escape(title)

    pdf = FPDF(orientation="portrait", unit="pt", format="Letter")
    pdf.set_margins(left=72, top=72, right=72)  # 1in margins
    pdf.set_auto_page_break(auto=True, margin=72)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    html_doc = (
        f"<h1>{safe_title}</h1>"
        f"{body_html}"
    )

    pdf.write_html(html_doc)

    output_path = get_artifact_path(run_id, artifact_id, "pdf")
    pdf.output(str(output_path))
    return output_path
