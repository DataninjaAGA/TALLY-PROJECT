from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from .models import TallyDocument, TallyTask
from .utils import format_short_date, one_line

PAGE_SIZE = landscape(letter)
PAGE_W, PAGE_H = PAGE_SIZE

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"
LIGHT_BLUE = colors.Color(0.74, 0.84, 0.95)


class TallyPDFGenerator:
    """Draws the Tally Sheet directly with ReportLab.

    The coordinates intentionally mirror the provided PDFs: landscape Letter, two
    side-by-side tables, signature area and copy block.
    """

    def __init__(self, logo_path: str | None = None):
        self.logo_path = Path(logo_path) if logo_path else None

    def build_pdf(self, document: TallyDocument) -> bytes:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)

        pages = self._paginate_tasks(document.tasks)
        total_pages = len(pages)
        for index, page_tasks in enumerate(pages, start=1):
            self._draw_page(c, document, page_tasks, page_no=index, total_pages=total_pages)
            c.showPage()

        c.save()
        return buffer.getvalue()

    def _paginate_tasks(self, tasks: list[TallyTask]) -> list[list[TallyTask]]:
        pages: list[list[TallyTask]] = []
        current: list[TallyTask] = []
        current_height = 0
        max_height = 315
        for task in tasks:
            height = self._row_height(task)
            if current and current_height + height > max_height:
                pages.append(current)
                current = []
                current_height = 0
            current.append(task)
            current_height += height
        if current:
            pages.append(current)
        return pages or [[]]

    def _row_height(self, task: TallyTask) -> int:
        desc_lines = self._wrap_text(task.description, 205, FONT, 7.4)
        task_lines = self._wrap_text(task.task_card, 72, FONT, 7.4)
        remark_lines = self._wrap_text(task.remark, 104, FONT, 7.4)
        line_count = max(len(desc_lines), len(task_lines), len(remark_lines), 1)
        return max(17, int(line_count * 8.6 + 10))

    def _draw_page(
        self,
        c: canvas.Canvas,
        document: TallyDocument,
        tasks: list[TallyTask],
        page_no: int,
        total_pages: int,
    ) -> None:
        c.setTitle(document.filename)
        self._draw_header(c, document)

        left_x = 52
        right_x = 505
        table_top_y = 455
        left_widths = [54, 86, 210, 46, 40]
        right_widths = [65, 80, 120]

        row_heights = [self._row_height(task) for task in tasks]
        self._draw_left_table(c, document.register, tasks, row_heights, left_x, table_top_y, left_widths)
        self._draw_right_table(c, tasks, row_heights, right_x, table_top_y, right_widths)

        bottom_y = table_top_y - 14 - sum(row_heights)
        self._draw_signature_and_footer(c, bottom_y, page_no, total_pages)

    def _draw_header(self, c: canvas.Canvas, document: TallyDocument) -> None:
        # Logo placeholder. Replace assets/logo.png to use a real logo.
        if self.logo_path and self.logo_path.exists():
            try:
                c.drawImage(str(self.logo_path), 62, 495, width=95, height=32, mask="auto", preserveAspectRatio=True)
            except Exception:
                self._draw_text_logo(c)
        else:
            self._draw_text_logo(c)

        c.setFont(FONT_BOLD, 10)
        c.drawCentredString(PAGE_W / 2, 502, "TALLY SHEET")

        c.setFont(FONT_BOLD, 8.5)
        c.drawString(520, 515, "STA")
        c.setFillColor(LIGHT_BLUE)
        c.rect(558, 509, 82, 12, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawCentredString(599, 512, document.station or "")

        c.drawString(612, 482, "DATE:")
        c.setFillColor(LIGHT_BLUE)
        c.rect(642, 476, 112, 12, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(646, 479, format_short_date(document.tally_date))

    def _draw_text_logo(self, c: canvas.Canvas) -> None:
        c.setFont(FONT_BOLD, 15)
        c.drawString(67, 492, "volaris")
        c.setFont(FONT_BOLD, 14)
        c.drawString(121, 506, "+")

    def _draw_left_table(
        self,
        c: canvas.Canvas,
        register: str,
        tasks: list[TallyTask],
        row_heights: list[int],
        x: int,
        top_y: int,
        widths: list[int],
    ) -> None:
        header_h = 14
        total_w = sum(widths)
        body_h = sum(row_heights)
        y = top_y

        c.setFont(FONT_OBLIQUE, 8.5)
        c.drawCentredString(x + widths[0] + (total_w - widths[0]) / 2, y + 5, "MAINTENANCE ACTIVITY")

        # Header row
        headers = ["REGISTER", "TASK CARD", "DESCRIPTION", "M/H", "WO"]
        c.setFont(FONT_BOLD, 8)
        cx = x
        for width, header in zip(widths, headers):
            c.rect(cx, y - header_h, width, header_h, stroke=1, fill=0)
            c.drawCentredString(cx + width / 2, y - 10, header)
            cx += width

        body_top = y - header_h
        body_bottom = body_top - body_h

        # Register merged cell
        c.rect(x, body_bottom, widths[0], body_h, stroke=1, fill=0)
        c.setFont(FONT, 8)
        c.drawCentredString(x + widths[0] / 2, body_bottom + body_h / 2 - 3, register)

        y_cursor = body_top
        for task, height in zip(tasks, row_heights):
            y_next = y_cursor - height
            cx = x + widths[0]
            # Task card
            c.rect(cx, y_next, widths[1], height, stroke=1, fill=0)
            self._draw_wrapped(c, task.task_card, cx + 3, y_next, widths[1] - 6, height, align="center")
            cx += widths[1]
            # Description
            c.rect(cx, y_next, widths[2], height, stroke=1, fill=0)
            self._draw_wrapped(c, task.description, cx + 3, y_next, widths[2] - 6, height, align="left")
            cx += widths[2]
            # M/H
            c.rect(cx, y_next, widths[3], height, stroke=1, fill=0)
            self._draw_wrapped(c, task.man_hours, cx + 3, y_next, widths[3] - 6, height, align="center")
            cx += widths[3]
            # WO
            c.rect(cx, y_next, widths[4], height, stroke=1, fill=0)
            self._draw_wrapped(c, one_line(task.work_order), cx + 2, y_next, widths[4] - 4, height, align="center")
            y_cursor = y_next

    def _draw_right_table(
        self,
        c: canvas.Canvas,
        tasks: list[TallyTask],
        row_heights: list[int],
        x: int,
        top_y: int,
        widths: list[int],
    ) -> None:
        header_h = 14
        headers = ["STATUS", "LOGBOOK PG.", "REMARK"]
        c.setFont(FONT_BOLD, 8)
        cx = x
        for width, header in zip(widths, headers):
            c.rect(cx, top_y - header_h, width, header_h, stroke=1, fill=0)
            c.drawCentredString(cx + width / 2, top_y - 10, header)
            cx += width

        y_cursor = top_y - header_h
        for task, height in zip(tasks, row_heights):
            y_next = y_cursor - height
            cx = x
            c.rect(cx, y_next, widths[0], height, stroke=1, fill=0)
            self._draw_wrapped(c, task.status, cx + 3, y_next, widths[0] - 6, height, align="center")
            cx += widths[0]
            c.rect(cx, y_next, widths[1], height, stroke=1, fill=0)
            self._draw_wrapped(c, task.logbook_pg, cx + 3, y_next, widths[1] - 6, height, align="center")
            cx += widths[1]
            c.rect(cx, y_next, widths[2], height, stroke=1, fill=0)
            self._draw_wrapped(c, task.remark, cx + 3, y_next, widths[2] - 6, height, align="center")
            y_cursor = y_next

    def _draw_signature_and_footer(self, c: canvas.Canvas, table_bottom_y: float, page_no: int, total_pages: int) -> None:
        sig_y = max(72, table_bottom_y - 24)
        c.setFont(FONT, 8)
        c.drawString(112, table_bottom_y - 9, "PLANNING, CONTROL AND RECORDS")
        c.drawString(112, table_bottom_y - 19, "ENGINNER")
        c.line(95, sig_y, 443, sig_y)
        c.drawCentredString(269, sig_y - 12, "NAME AND SIGNATURE")

        c.drawCentredString(616, table_bottom_y - 9, "MAINTENANCE SUPERVISOR ON DUTY")
        c.line(505, sig_y, 702, sig_y)
        c.drawCentredString(604, sig_y - 12, "NAME AND SIGNATURE")

        c.drawString(55, 72, "Copy to:")
        c.drawString(55, 61, "Maintenance Control Center")
        c.drawString(55, 50, "Quality Control Chief")
        c.drawString(55, 39, "Stockroom Chief")

        c.drawRightString(754, 48, "VOI-THS-126")
        c.drawRightString(754, 37, "REV. 1 21 ENE 2013")
        if total_pages > 1:
            c.drawRightString(754, 25, f"Page {page_no} of {total_pages}")

    def _wrap_text(self, text: str, width: float, font_name: str, font_size: float) -> list[str]:
        if not text:
            return [""]
        final_lines: list[str] = []
        for raw_line in str(text).split("\n"):
            words = raw_line.split()
            if not words:
                final_lines.append("")
                continue
            line = ""
            for word in words:
                candidate = word if not line else f"{line} {word}"
                if stringWidth(candidate, font_name, font_size) <= width:
                    line = candidate
                else:
                    if line:
                        final_lines.append(line)
                    line = word
            if line:
                final_lines.append(line)
        return final_lines or [""]

    def _draw_wrapped(
        self,
        c: canvas.Canvas,
        text: str,
        x: float,
        y_bottom: float,
        width: float,
        height: float,
        align: str = "left",
    ) -> None:
        font_size = 7.4
        line_h = 8.6
        lines = self._wrap_text(text, width, FONT, font_size)
        block_h = len(lines) * line_h
        y = y_bottom + max((height - block_h) / 2, 2) + block_h - line_h
        c.setFont(FONT, font_size)
        for line in lines:
            if y < y_bottom + 1:
                break
            if align == "center":
                c.drawCentredString(x + width / 2, y, line)
            else:
                c.drawString(x, y, line)
            y -= line_h


def build_pdf_bytes(document: TallyDocument, logo_path: str | None = None) -> bytes:
    return TallyPDFGenerator(logo_path=logo_path).build_pdf(document)


def build_many_pdfs(documents: Iterable[TallyDocument], logo_path: str | None = None) -> dict[str, bytes]:
    generator = TallyPDFGenerator(logo_path=logo_path)
    return {doc.filename: generator.build_pdf(doc) for doc in documents}
