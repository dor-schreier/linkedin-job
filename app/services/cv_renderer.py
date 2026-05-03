"""CV Renderer — produces PDF bytes and JSON dict from a CVData model."""
from __future__ import annotations

import logging
from pathlib import Path

from app.schemas import CVData

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "cv_export" / "templates" / "cv"


def render_cv_html(cv: CVData, template_name: str = "default") -> str:
    """Render CV data to an HTML string using Jinja2."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
    template = env.get_template(f"{template_name}.html")
    return template.render(cv=cv)


def render_cv_pdf(cv: CVData, template_name: str = "default") -> bytes:
    """Render CV to PDF bytes via WeasyPrint."""
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise ImportError(
            "weasyprint is required for PDF rendering. Run: pip install weasyprint"
        ) from exc

    html_str = render_cv_html(cv, template_name)
    pdf_bytes = HTML(string=html_str, base_url=str(_TEMPLATE_DIR)).write_pdf()
    return pdf_bytes


def render_cv_json(cv: CVData) -> dict:
    """Serialise CVData to a plain dict with ISO-formatted dates."""
    return cv.model_dump()
