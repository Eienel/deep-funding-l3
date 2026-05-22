"""Render WRITEUP.md into a plain black-and-white WRITEUP.pdf.

A small markdown-to-PDF converter (headings, paragraphs, bullet and numbered
lists, fenced code blocks, simple tables). ASCII only, built-in fonts, no
colors. Run: python build_writeup_pdf.py
"""

from __future__ import annotations

import re

from fpdf import FPDF
from fpdf.enums import XPos, YPos

BLACK = (0, 0, 0)
GREY = (110, 110, 110)

LM, RM = XPos.LMARGIN, XPos.RIGHT
NEXT, TOP = YPos.NEXT, YPos.TOP

SRC = "WRITEUP.md"
OUT = "WRITEUP.pdf"


class Doc(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 8, "Deep Funding Level III - Writeup", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x=LM, new_y=NEXT)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 10, "deep-funding-l3  -  joinpond.ai", align="C")


def clean(text: str) -> str:
    return text.replace("`", "")


def h1(pdf: Doc, text: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(0, 8, clean(text), new_x=LM, new_y=NEXT)
    pdf.ln(3)


def h2(pdf: Doc, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(0, 7, clean(text), new_x=LM, new_y=NEXT)
    pdf.ln(2)


def para(pdf: Doc, text: str) -> None:
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(0, 6, clean(text), new_x=LM, new_y=NEXT)
    pdf.ln(2)


def list_item(pdf: Doc, marker: str, text: str) -> None:
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*BLACK)
    pdf.set_x(pdf.l_margin + 4)
    pdf.cell(7, 6, marker, new_x=RM, new_y=TOP)
    pdf.multi_cell(0, 6, clean(text), new_x=LM, new_y=NEXT)


def code_block(pdf: Doc, lines: list[str]) -> None:
    pdf.ln(1)
    pdf.set_font("Courier", "", 9.5)
    pdf.set_text_color(*BLACK)
    pdf.set_x(pdf.l_margin + 4)
    pdf.multi_cell(0, 5.5, "\n".join(lines), border=0, align="L",
                   new_x=LM, new_y=NEXT)
    pdf.ln(2)


def table(pdf: Doc, rows: list[list[str]]) -> None:
    pdf.ln(1)
    widths = [100, 70]
    pdf.set_draw_color(*BLACK)
    pdf.set_line_width(0.2)
    for i, row in enumerate(rows):
        style = "B" if i == 0 else ""
        pdf.set_font("Helvetica", style, 11)
        pdf.set_text_color(*BLACK)
        for j, cell in enumerate(row[:2]):
            last = j == 1
            pdf.cell(widths[j], 8, "  " + clean(cell), border=1,
                     new_x=(LM if last else RM), new_y=(NEXT if last else TOP))
    pdf.ln(3)


def is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|?", line.strip()))


def split_row(line: str) -> list[str]:
    parts = line.strip().strip("|").split("|")
    return [p.strip() for p in parts]


def build() -> None:
    with open(SRC, encoding="utf-8") as f:
        lines = f.readlines()

    pdf = Doc()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(20, 18, 20)
    pdf.add_page()

    mode = None
    buf: list[str] = []
    tbl: list[list[str]] = []

    def flush():
        nonlocal mode, buf, tbl
        if mode == "para" and buf:
            para(pdf, " ".join(buf))
        elif mode == "table" and tbl:
            table(pdf, tbl)
        buf, tbl, mode = [], [], None

    in_code = False
    code_buf: list[str] = []

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                code_block(pdf, code_buf)
                code_buf, in_code = [], False
            else:
                code_buf.append(line)
            continue

        if stripped.startswith("```"):
            flush()
            in_code = True
            continue

        if stripped == "":
            flush()
            continue

        if line.startswith("# "):
            flush()
            h1(pdf, line[2:])
            continue
        if line.startswith("## "):
            flush()
            h2(pdf, line[3:])
            continue

        if line.startswith("|"):
            if is_separator(line):
                continue
            tbl.append(split_row(line))
            mode = "table"
            continue

        m_bullet = re.match(r"^- (.*)", line)
        m_number = re.match(r"^(\d+)\. (.*)", line)

        if m_bullet:
            flush()
            list_item(pdf, "-", m_bullet.group(1))
            mode = "list"
            continue
        if m_number:
            flush()
            list_item(pdf, m_number.group(1) + ".", m_number.group(2))
            mode = "list"
            continue

        if raw.startswith((" ", "\t")):
            if mode == "list":
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(*BLACK)
                pdf.set_x(pdf.l_margin + 11)
                pdf.multi_cell(0, 6, clean(stripped), new_x=LM, new_y=NEXT)
                continue
            if mode == "para":
                buf.append(stripped)
                continue
            buf = [stripped]
            mode = "para"
            continue

        if mode not in (None, "para"):
            flush()
        buf.append(stripped)
        mode = "para"

    flush()
    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
