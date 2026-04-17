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
from unidecode import unidecode

from src.store.artifacts_dir import get_artifact_path


# Common unicode glyphs the LLM loves to emit, mapped to visually-similar
# ASCII. Applied before `unidecode` so we can control the most frequent
# substitutions tightly (avoids unidecode mangling things like em-dashes).
_GLYPH_MAP: dict[str, str] = {
    "\u2018": "'", "\u2019": "'",         # curly single quotes
    "\u201c": '"', "\u201d": '"',         # curly double quotes
    "\u2013": "-", "\u2014": "--",        # en / em dash
    "\u2026": "...",                      # ellipsis
    "\u2022": "*",                        # bullet
    "\u2192": "->", "\u2190": "<-",       # arrows
    "\u00a0": " ",                        # non-breaking space
}


def _to_latin1_safe(text: str) -> str:
    """Make `text` safe for fpdf2's built-in Helvetica (Latin-1 only)."""
    for src, dst in _GLYPH_MAP.items():
        text = text.replace(src, dst)
    # unidecode handles anything else (accents, CJK, symbols) by
    # transliterating to ASCII. Pure Python, no font files needed.
    return unidecode(text)


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
    # Sanitise BEFORE markdown so non-Latin-1 chars never reach fpdf.
    content_md = _to_latin1_safe(content_md)
    title = _to_latin1_safe(title)

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
