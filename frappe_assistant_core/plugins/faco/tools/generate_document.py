# Frappe Assistant Core - Document Generation Tools
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Generate Document Tool — converts markdown content to a downloadable PDF.

Uses Frappe's built-in markdown2 (md_to_html) for markdown conversion,
and WeasyPrint (preferred) or wkhtmltopdf (fallback) for PDF rendering.
No additional dependencies required.
"""

import os
import re
from typing import Any, ClassVar

import frappe
from frappe import _
from frappe.utils import now_datetime

from frappe_assistant_core.core.base_tool import BaseTool
from frappe_assistant_core.plugins.faco.tools.rich_blocks import (
    preprocess_rich_blocks,
    restore_rich_blocks,
)


class GenerateDocument(BaseTool):
    """
    MCP tool that generates a downloadable PDF from markdown content.

    The agent writes markdown (tables, headings, lists, code blocks) and this
    tool converts it to a styled PDF, saves it as a private Frappe File, and
    returns the download URL for the agent to share with the user.
    """

    def __init__(self):
        super().__init__()
        self.name = "generate_document"
        self.description = (
            "Generate a downloadable PDF from markdown content (headings, tables, lists, code blocks). "
            "Write complete, well-structured markdown — it becomes the whole document. "
            "RICH BLOCKS: embed ```chart```, ```callout```, ```metric```, ```cover```, ```pagebreak``` "
            "fences for inline SVG charts, call-outs, KPI cards, cover pages, and page breaks; chart "
            "schema matches the chat-side dialect. See the 'document_authoring' skill for a full guide. "
            "LINK FORMAT: copy the result's 'download_link' VERBATIM, e.g. [Report.pdf](/private/files/Report.pdf) "
            "— no 'sandbox:' or 'https://' prefix."
        )
        self.source_app = "frappe_assistant_core"
        self.category = "Document"
        self.requires_permission = None

        self.inputSchema = {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Document body in markdown (headings, tables, lists, code blocks, etc.)",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename without extension; .pdf is added automatically",
                },
                "title": {
                    "type": "string",
                    "description": "Optional styled header at the top of the PDF",
                },
                "orientation": {
                    "type": "string",
                    "enum": ["portrait", "landscape"],
                    "default": "portrait",
                    "description": "Use 'landscape' for wide tables or charts",
                },
                "page_size": {
                    "type": "string",
                    "enum": ["A4", "Letter"],
                    "default": "A4",
                    "description": "Paper size",
                },
            },
            "required": ["content", "filename"],
        }

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Generate PDF from markdown content and return the file URL."""
        try:
            content = arguments.get("content", "")
            filename = arguments.get("filename", "document")
            title = arguments.get("title")
            orientation = arguments.get("orientation", "portrait")
            page_size = arguments.get("page_size", "A4")

            if not content.strip():
                return {"success": False, "error": "Content cannot be empty."}

            # Sanitize filename
            safe_filename = self._sanitize_filename(filename)

            # Convert markdown to HTML, then sanitize. FACO-M9: md_to_html
            # returns markupsafe.Markup which Jinja inserts verbatim. Any
            # raw HTML in the LLM's markdown output (including script,
            # onerror, javascript: URIs) would otherwise survive straight
            # into the rendering pipeline — benign for WeasyPrint today but
            # unsafe the moment the renderer changes (wkhtmltopdf executes
            # script; browser preview of the PDF URL can too).
            #
            # Rich-block fences (```chart```, ```callout```, ```metric```,
            # ```cover```, ```pagebreak```) are pulled out *before* the
            # bleach pass, replaced with opaque tokens, and substituted
            # back in *after* sanitisation. The rendered HTML we emit for
            # these blocks contains inline SVG and inline styles that
            # bleach would otherwise strip — but it's trusted because we
            # generated it ourselves, not the LLM.
            content_with_tokens, rich_tokens = preprocess_rich_blocks(content)
            sanitised = self._sanitize_html(frappe.utils.md_to_html(content_with_tokens) or "")
            html_body = restore_rich_blocks(sanitised, rich_tokens)

            # Build full HTML document from template
            full_html = self._render_template(
                body=html_body,
                title=title,
                orientation=orientation,
                page_size=page_size,
            )

            # Generate PDF (WeasyPrint preferred, wkhtmltopdf fallback)
            pdf_bytes = self._generate_pdf(full_html, page_size, orientation)

            # Save as private file
            pdf_filename = f"{safe_filename}.pdf"
            file_doc = frappe.get_doc(
                {
                    "doctype": "File",
                    "file_name": pdf_filename,
                    "content": pdf_bytes,
                    "is_private": 1,
                }
            )
            file_doc.save(ignore_permissions=True)

            file_size = len(pdf_bytes)

            return {
                "success": True,
                "file_url": file_doc.file_url,
                "file_name": pdf_filename,
                "file_size": file_size,
                "file_size_display": self._format_file_size(file_size),
                "download_link": f"[{pdf_filename}]({file_doc.file_url})",
                "message": (
                    f"PDF generated: {pdf_filename} ({self._format_file_size(file_size)}). "
                    f"Copy this markdown link VERBATIM into your response (do NOT add sandbox: or any prefix): "
                    f"[{pdf_filename}]({file_doc.file_url})"
                ),
            }

        except Exception as e:
            frappe.log_error(
                title=_("Generate Document Error"),
                message=f"Error generating PDF: {e!s}",
            )
            return {"success": False, "error": str(e)}

    # FACO-M9: tags allowed in the PDF body. Covers CommonMark output from
    # md_to_html; everything else is stripped. No ``script``, no ``iframe``,
    # no event attributes. ``href`` is schemed to http(s)/mailto/relative.
    _ALLOWED_TAGS: ClassVar[set[str]] = {
        "p",
        "br",
        "hr",
        "blockquote",
        "pre",
        "code",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "th",
        "td",
        "strong",
        "em",
        "b",
        "i",
        "u",
        "s",
        "del",
        "sub",
        "sup",
        "a",
        "span",
        "div",
        "img",
    }
    _ALLOWED_ATTRS: ClassVar[dict[str, list[str]]] = {
        "a": ["href", "title"],
        "img": ["src", "alt", "title", "width", "height"],
        "span": ["class"],
        "div": ["class"],
        "th": ["align"],
        "td": ["align"],
    }
    _ALLOWED_PROTOCOLS: ClassVar[set[str]] = {"http", "https", "mailto", "data"}

    def _sanitize_html(self, html: str) -> str:
        """Strip dangerous HTML from LLM-generated markdown output."""
        try:
            import bleach
        except ImportError:
            # bleach is a stdlib-adjacent dependency of Frappe; if it isn't
            # available we fall back to a conservative strip-all so we
            # never ship unsanitized HTML into the PDF pipeline.
            import re as _re

            return _re.sub(r"<[^>]*>", "", html)
        return bleach.clean(
            html,
            tags=self._ALLOWED_TAGS,
            attributes=self._ALLOWED_ATTRS,
            protocols=self._ALLOWED_PROTOCOLS,
            strip=True,
            strip_comments=True,
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Remove unsafe characters from filename, preserving readability."""
        # Strip leading/trailing whitespace
        name = filename.strip()
        # Remove path separators and null bytes
        name = re.sub(r"[/\\:\x00]", "", name)
        # Replace other unsafe chars with underscores
        name = re.sub(r'[<>"|?*]', "_", name)
        # Collapse multiple spaces/underscores
        name = re.sub(r"[\s_]+", "_", name)
        # Remove leading dots (hidden files)
        name = name.lstrip(".")
        # Fallback
        if not name:
            name = "document"
        # Truncate to reasonable length
        return name[:200]

    def _render_template(
        self, body: str, title: str | None = None, orientation: str = "portrait", page_size: str = "A4"
    ) -> str:
        """Render the PDF HTML template with the given content."""
        template_path = os.path.join(
            frappe.get_app_path("frappe_assistant_core"),
            "plugins",
            "faco",
            "tools",
            "templates",
            "document_pdf.html",
        )

        # template_path is built from frappe.get_app_path() + hard-coded
        # segments; no user input participates, so traversal is unreachable.
        with open(template_path) as f:  # nosemgrep: frappe-security-file-traversal
            template_string = f.read()

        generated_date = now_datetime().strftime("%B %d, %Y at %I:%M %p")

        context = {
            "body": body,
            "title": title,
            "subtitle": None,
            "generated_date": generated_date,
            "page_size": page_size,
            "orientation": orientation.capitalize() if orientation == "landscape" else None,
            "margin_top": "15mm",
            "margin_bottom": "20mm",
            "margin_left": "15mm",
            "margin_right": "15mm",
        }

        # template_string is the shipped document_pdf.html, never user input.
        # `body` is bleach-sanitized via _sanitize_html before reaching context.
        return frappe.render_template(template_string, context)  # nosemgrep: frappe-ssti

    def _generate_pdf(self, html: str, page_size: str, orientation: str) -> bytes:
        """
        Generate PDF bytes from HTML.

        Tries WeasyPrint first (pure Python, works on all architectures including
        Apple Silicon). Falls back to wkhtmltopdf via Frappe's get_pdf() if
        WeasyPrint is unavailable.
        """
        # Try WeasyPrint first
        try:
            from weasyprint import CSS
            from weasyprint import HTML as WeasyHTML

            # WeasyPrint uses @page CSS for page size/orientation
            page_css = (
                f"@page {{ size: {page_size} {'landscape' if orientation == 'landscape' else 'portrait'}; }}"
            )
            doc = WeasyHTML(string=html, base_url=frappe.utils.get_url()).render(
                stylesheets=[CSS(string=page_css)]
            )
            return doc.write_pdf()
        except ImportError:
            pass
        except Exception as e:
            self.logger.warning(f"WeasyPrint failed, falling back to wkhtmltopdf: {e}")

        # Fallback to wkhtmltopdf
        pdf_options = {
            "page-size": page_size,
            "orientation": "Landscape" if orientation == "landscape" else "Portrait",
            "print-media-type": None,
            "background": None,
            "images": None,
            "encoding": "UTF-8",
        }
        return frappe.utils.pdf.get_pdf(html, options=pdf_options)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format bytes into human-readable size."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


# Module-level alias for tool discovery
generate_document = GenerateDocument
