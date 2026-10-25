"""CSV and PDF exports built from real workspace data."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer
    PDF_AVAILABLE = True
except ImportError:  # optional dependency
    PDF_AVAILABLE = False


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")  # BOM so Excel opens UTF-8 correctly


def brief_to_pdf(brief: dict) -> bytes | None:
    if not PDF_AVAILABLE:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title=brief["title"])
    ss = getSampleStyleSheet()
    navy, teal = colors.HexColor("#111827"), colors.HexColor("#0D9488")
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=navy, fontSize=18, alignment=0, spaceAfter=4)
    meta = ParagraphStyle("meta", parent=ss["Normal"], textColor=colors.HexColor("#6B7280"), fontSize=8.5)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=teal, fontSize=12.5, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["Normal"], fontSize=9.5, leading=13)
    story = [Paragraph(escape(brief["title"]), h1),
             Paragraph(escape(f"Generated {brief['generated_at']} by AniScope AI · decision support, not independently verified"), meta),
             Spacer(1, 6)]
    for i, (head, items) in enumerate(brief["sections"].items(), 1):
        story.append(Paragraph(f"{i}. {escape(head)}", h2))
        if len(items) == 1:
            story.append(Paragraph(escape(str(items[0])), body))
        else:
            story.append(ListFlowable([ListItem(Paragraph(escape(str(x)), body), leftIndent=10) for x in items],
                                      bulletType="bullet", start="•", leftIndent=10))
    doc.build(story)
    return buf.getvalue()
