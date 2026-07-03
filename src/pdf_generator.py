from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .models import TallyDocument, TallyTask
from .utils import format_short_date, one_line

PAGE_SIZE = landscape(letter)
PAGE_W, PAGE_H = PAGE_SIZE

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_OBLIQUE = "Helvetica-Oblique"
LIGHT_BLUE = colors.Color(0.74, 0.84, 0.95)

# Main layout constants. The tally is intentionally kept on one page.
LEFT_X = 52
RIGHT_X = 505
TABLE_TOP_Y = 455
HEADER_H = 14
LEFT_WIDTHS = [54, 86, 210, 46, 40]
RIGHT_WIDTHS = [65, 80, 120]
MIN_TABLE_BOTTOM_Y = 150
MIN_FONT_SIZE = 4.8
MAX_FONT_SIZE = 7.4
SIGNATURE_LINE_GAP = 44

# Vertical centering controls.
# All coordinates are PDF points, with origin at the bottom-left.
# The objective is not to center against the full sheet, because the footer
# remains fixed at the bottom. Instead, the operational body is centered in the
# usable middle area of the page.
CONTENT_TOP_Y = 543          # Top of the logo/header block in the original layout.
CONTENT_MAX_TOP_Y = 568      # Avoid pushing the logo too close to the top edge.
CONTENT_MIN_BOTTOM_Y = 92    # Avoid colliding with the fixed footer.
TARGET_BODY_CENTER_Y = 350   # Visual center of the main tally body area.


@dataclass(frozen=True)
class RowLayout:
    row_heights: list[float]
    font_size: float
    line_height: float


class TallyPDFGenerator:
    """Draws one official-looking Tally Sheet directly with ReportLab.

    Important business rules implemented here:
    - One register produces one PDF page only.
    - Up to 14 task cards are compressed to fit in the same page.
    - Signature lines are placed lower than the label text to leave signing room.
    - The Volaris logo is loaded from assets/logo.png when available.
    - The main tally body is vertically centered according to the number of tasks.
    """

    def __init__(self, logo_path: str | None = None):
        self.logo_path = Path(logo_path) if logo_path else None

    def build_pdf(self, document: TallyDocument) -> bytes:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
        c.setTitle(document.filename)
        self._draw_page(c, document)
        c.save()
        return buffer.getvalue()

    def _draw_page(self, c: canvas.Canvas, document: TallyDocument) -> None:
        tasks = document.tasks[:14]
        layout = self._calculate_row_layout(tasks)

        y_offset = self._calculate_vertical_offset(layout)
        table_top_y = TABLE_TOP_Y + y_offset

        self._draw_header(c, document, y_offset=y_offset)
        self._draw_left_table(document.register, c, tasks, layout, LEFT_X, table_top_y, LEFT_WIDTHS)
        self._draw_right_table(c, tasks, layout, RIGHT_X, table_top_y, RIGHT_WIDTHS)

        bottom_y = table_top_y - HEADER_H - sum(layout.row_heights)
        self._draw_signature_and_footer(c, bottom_y)

    def _calculate_vertical_offset(self, layout: RowLayout) -> float:
        """Return the vertical movement needed to center the main tally body.

        Previous versions used a fixed TABLE_TOP_Y. That made short tallys stay
        glued to the upper half of the page. This function calculates the real
        height of the generated body and shifts the header/table/signature block
        so its visual center remains stable. The fixed footer is not moved.
        """
        body_h = sum(layout.row_heights)
        table_bottom_y = TABLE_TOP_Y - HEADER_H - body_h

        # This mirrors _draw_signature_and_footer() so the centering calculation
        # uses the actual lowest point of the movable body.
        line_y = max(88, table_bottom_y - SIGNATURE_LINE_GAP)
        content_bottom_y = line_y - 16

        current_center_y = (CONTENT_TOP_Y + content_bottom_y) / 2
        y_offset = TARGET_BODY_CENTER_Y - current_center_y

        # Safety limits: keep the movable body between page top and fixed footer.
        if CONTENT_TOP_Y + y_offset > CONTENT_MAX_TOP_Y:
            y_offset = CONTENT_MAX_TOP_Y - CONTENT_TOP_Y
        if content_bottom_y + y_offset < CONTENT_MIN_BOTTOM_Y:
            y_offset = CONTENT_MIN_BOTTOM_Y - content_bottom_y

        return y_offset

    def _calculate_row_layout(self, tasks: list[TallyTask]) -> RowLayout:
        """Calculate compact row heights so all tasks fit on one page.

        The first pass tries progressively smaller fonts. If a very dense tally
        still exceeds the available body height, the final pass proportionally
        compresses row heights while preserving at least one readable line.
        """
        if not tasks:
            return RowLayout(row_heights=[], font_size=MAX_FONT_SIZE, line_height=8.6)

        max_body_h = TABLE_TOP_Y - HEADER_H - MIN_TABLE_BOTTOM_Y
        font_candidates = [7.4, 7.0, 6.6, 6.2, 5.8, 5.4, 5.0, MIN_FONT_SIZE]

        best_heights: list[float] = []
        best_font_size = MIN_FONT_SIZE
        best_line_h = MIN_FONT_SIZE + 1.1

        for font_size in font_candidates:
            line_h = font_size + 1.2
            heights = [self._row_height(task, font_size, line_h) for task in tasks]
            best_heights = heights
            best_font_size = font_size
            best_line_h = line_h
            if sum(heights) <= max_body_h:
                return RowLayout(row_heights=heights, font_size=font_size, line_height=line_h)

        total_h = sum(best_heights)
        if total_h > max_body_h and total_h > 0:
            factor = max_body_h / total_h
            min_h = best_line_h + 5
            compressed = [max(min_h, h * factor) for h in best_heights]
            # If the minimum height pushed us over the limit, distribute evenly.
            if sum(compressed) > max_body_h:
                even_h = max_body_h / len(tasks)
                compressed = [even_h for _ in tasks]
            best_heights = compressed

        return RowLayout(row_heights=best_heights, font_size=best_font_size, line_height=best_line_h)

    def _row_height(self, task: TallyTask, font_size: float, line_h: float) -> float:
        desc_lines = self._wrap_text(task.description, 205, FONT, font_size)
        task_lines = self._wrap_text(task.task_card, 72, FONT, font_size)
        remark_lines = self._wrap_text(task.remark, 104, FONT, font_size)
        wo_lines = self._wrap_text(one_line(task.work_order), 36, FONT, font_size)
        line_count = max(len(desc_lines), len(task_lines), len(remark_lines), len(wo_lines), 1)
        return max(14, line_count * line_h + 7)

    def _draw_header(self, c: canvas.Canvas, document: TallyDocument, y_offset: float = 0) -> None:
        if self.logo_path and self.logo_path.exists():
            try:
                c.drawImage(
                    str(self.logo_path),
                    62,
                    493 + y_offset,
                    width=108,
                    height=50,
                    mask="auto",
                    preserveAspectRatio=True,
                    anchor="sw",
                )
            except Exception:
                self._draw_text_logo(c, y_offset=y_offset)
        else:
            self._draw_text_logo(c, y_offset=y_offset)

        c.setFont(FONT_BOLD, 10)
        c.drawCentredString(PAGE_W / 2, 502 + y_offset, "TALLY SHEET")

        c.setFont(FONT_BOLD, 8.5)
        c.drawString(520, 515 + y_offset, "STA")
        c.setFillColor(LIGHT_BLUE)
        c.rect(558, 509 + y_offset, 82, 12, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawCentredString(599, 512 + y_offset, document.station or "")

        c.drawString(612, 482 + y_offset, "DATE:")
        c.setFillColor(LIGHT_BLUE)
        c.rect(642, 476 + y_offset, 112, 12, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.drawString(646, 479 + y_offset, format_short_date(document.tally_date))

    def _draw_text_logo(self, c: canvas.Canvas, y_offset: float = 0) -> None:
        c.setFont(FONT_BOLD, 15)
        c.drawString(67, 492 + y_offset, "volaris")
        c.setFont(FONT_BOLD, 14)
        c.drawString(121, 506 + y_offset, "+")

    def _draw_left_table(
        self,
        register: str,
        c: canvas.Canvas,
        tasks: list[TallyTask],
        layout: RowLayout,
        x: int,
        top_y: float,
        widths: list[int],
    ) -> None:
        total_w = sum(widths)
        body_h = sum(layout.row_heights)
        y = top_y

        c.setFont(FONT_OBLIQUE, 8.5)
        c.drawCentredString(x + widths[0] + (total_w - widths[0]) / 2, y + 5, "MAINTENANCE ACTIVITY")

        headers = ["REGISTER", "TASK CARD", "DESCRIPTION", "M/H", "WO"]
        c.setFont(FONT_BOLD, 8)
        cx = x
        for width, header in zip(widths, headers):
            c.rect(cx, y - HEADER_H, width, HEADER_H, stroke=1, fill=0)
            c.drawCentredString(cx + width / 2, y - 10, header)
            cx += width

        body_top = y - HEADER_H
        body_bottom = body_top - body_h

        c.rect(x, body_bottom, widths[0], body_h, stroke=1, fill=0)
        c.setFont(FONT, 8)
        c.drawCentredString(x + widths[0] / 2, body_bottom + body_h / 2 - 3, register)

        y_cursor = body_top
        for task, height in zip(tasks, layout.row_heights):
            y_next = y_cursor - height
            cx = x + widths[0]

            c.rect(cx, y_next, widths[1], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                task.task_card,
                cx + 3,
                y_next,
                widths[1] - 6,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="center",
            )
            cx += widths[1]

            c.rect(cx, y_next, widths[2], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                task.description,
                cx + 3,
                y_next,
                widths[2] - 6,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="left",
            )
            cx += widths[2]

            c.rect(cx, y_next, widths[3], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                task.man_hours,
                cx + 3,
                y_next,
                widths[3] - 6,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="center",
            )
            cx += widths[3]

            c.rect(cx, y_next, widths[4], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                one_line(task.work_order),
                cx + 2,
                y_next,
                widths[4] - 4,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="center",
            )
            y_cursor = y_next

    def _draw_right_table(
        self,
        c: canvas.Canvas,
        tasks: list[TallyTask],
        layout: RowLayout,
        x: int,
        top_y: float,
        widths: list[int],
    ) -> None:
        headers = ["STATUS", "LOGBOOK PG.", "REMARK"]
        c.setFont(FONT_BOLD, 8)
        cx = x
        for width, header in zip(widths, headers):
            c.rect(cx, top_y - HEADER_H, width, HEADER_H, stroke=1, fill=0)
            c.drawCentredString(cx + width / 2, top_y - 10, header)
            cx += width

        y_cursor = top_y - HEADER_H
        for task, height in zip(tasks, layout.row_heights):
            y_next = y_cursor - height
            cx = x

            c.rect(cx, y_next, widths[0], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                task.status,
                cx + 3,
                y_next,
                widths[0] - 6,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="center",
            )
            cx += widths[0]

            c.rect(cx, y_next, widths[1], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                task.logbook_pg,
                cx + 3,
                y_next,
                widths[1] - 6,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="center",
            )
            cx += widths[1]

            c.rect(cx, y_next, widths[2], height, stroke=1, fill=0)
            self._draw_wrapped(
                c,
                task.remark,
                cx + 3,
                y_next,
                widths[2] - 6,
                height,
                font_size=layout.font_size,
                line_h=layout.line_height,
                align="center",
            )
            y_cursor = y_next

    def _draw_signature_and_footer(self, c: canvas.Canvas, table_bottom_y: float) -> None:
        left_label_y = table_bottom_y - 9
        line_y = max(88, table_bottom_y - SIGNATURE_LINE_GAP)

        c.setFont(FONT, 8)
        c.drawString(112, left_label_y, "PLANNING, CONTROL AND RECORDS")
        c.drawString(112, left_label_y - 10, "ENGINNER")
        c.line(95, line_y, 443, line_y)
        c.drawCentredString(269, line_y - 12, "NAME AND SIGNATURE")

        c.drawCentredString(616, left_label_y, "MAINTENANCE SUPERVISOR ON DUTY")
        c.line(505, line_y, 702, line_y)
        c.drawCentredString(604, line_y - 12, "NAME AND SIGNATURE")

        c.drawString(55, 72, "Copy to:")
        c.drawString(55, 61, "Maintenance Control Center")
        c.drawString(55, 50, "Quality Control Chief")
        c.drawString(55, 39, "Stockroom Chief")

        c.drawRightString(754, 48, "VOI-THS-126")
        c.drawRightString(754, 37, "REV. 1 21 ENE 2013")

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
                    # Long single tokens are kept as-is; they are usually task-card IDs.
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
        font_size: float,
        line_h: float,
        align: str = "left",
    ) -> None:
        lines = self._wrap_text(text, width, FONT, font_size)
        block_h = len(lines) * line_h
        y = y_bottom + max((height - block_h) / 2, 1.5) + block_h - line_h
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
