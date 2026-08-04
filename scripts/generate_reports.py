#!/usr/bin/env python3
"""Generate the static percentage-only R6E8A PDF reports."""

from pathlib import Path
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "downloads"
W, H = letter

BG = HexColor("#001b14")
PANEL = HexColor("#003126")
PANEL_DARK = HexColor("#010504")
LINE = HexColor("#286151")
INK = HexColor("#f8fffb")
MUTED = HexColor("#b8d0c6")
GREEN = HexColor("#66e47a")
BLUE = HexColor("#55b9ef")
AMBER = HexColor("#f5c63d")
RED = HexColor("#ef5148")
CREAM = HexColor("#fff8df")
CREAM_INK = HexColor("#493206")

RC_SERIES = [
    145,138,70,71,164,152,89,78,110,163,111,154,85,133,147,86,85,85,170,
    127,90,92,92,95,100,170,105,96,92,91,172,111,92,95,94,154,133,90,90,
    90,94,155,109,96,95,97,96,105,164,114,94,96,93,118,159,92,93,95,115,
    162,111,93,109,164,109,142,165,134,92,92,94,91,88,93,91,92,91,
]


def panel(c, x, y, width, height, fill=PANEL, radius=10):
    c.setFillColor(fill)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.roundRect(x, y, width, height, radius, fill=1, stroke=1)


def text(c, value, x, y, size=10, color=INK, font="Helvetica", anchor="left"):
    c.setFillColor(color)
    c.setFont(font, size)
    if anchor == "right":
        c.drawRightString(x, y, value)
    elif anchor == "center":
        c.drawCentredString(x, y, value)
    else:
        c.drawString(x, y, value)


def wrap(value, width, size, font="Helvetica"):
    words = value.split()
    lines, line = [], ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if stringWidth(candidate, font, size) <= width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def paragraph(c, value, x, y, width, size=9, leading=12, color=MUTED, font="Helvetica", max_lines=None):
    lines = wrap(value, width, size, font)
    if max_lines:
        lines = lines[:max_lines]
    for idx, line in enumerate(lines):
        text(c, line, x, y - idx * leading, size, color, font)
    return y - len(lines) * leading


def tag(c, value, x, y, color=GREEN):
    text(c, value.upper(), x, y, 7.3, color, "Helvetica-Bold")


def page_base(c, report_name, page):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    text(c, "UNIT 2709  /  R6E8A  /  APRIL 12, 2026 - ONGOING", 34, H - 28, 7.2, GREEN, "Helvetica-Bold")
    text(c, report_name, W - 34, H - 28, 7.2, MUTED, "Helvetica-Bold", "right")
    c.setStrokeColor(LINE)
    c.line(34, 25, W - 34, 25)
    text(c, "R6E8A percentage-only published-guide index", 34, 12, 7, MUTED)
    text(c, f"Page {page}", W - 34, 12, 7, MUTED, "Helvetica", "right")


def draw_index_card(c, x, y, width, height, number, family, title, copy, hot=False):
    panel(c, x, y, width, height)
    tag(c, family, x + 12, y + height - 17)
    text(c, title, x + 12, y + height - 35, 10.5, INK, "Helvetica-Bold")
    text(c, number, x + 12, y + height - 73, 27, RED if hot else GREEN, "Helvetica-Bold")
    track_x, track_y, track_w = x + 12, y + 32, width - 24
    c.setFillColor(HexColor("#123f33"))
    c.roundRect(track_x, track_y, track_w, 12, 3, fill=1, stroke=0)
    value = int(number.replace("%", ""))
    fill_w = track_w * min(value, 200) / 200
    c.setFillColor(RED if hot else GREEN)
    c.roundRect(track_x, track_y, fill_w, 12, 3, fill=1, stroke=0)
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    guide_x = track_x + track_w / 2
    c.line(guide_x, track_y - 1, guide_x, track_y + 13)
    paragraph(c, copy, x + 12, y + 20, width - 24, 7.5, 9, MUTED, max_lines=2)


def page_one(c, report_name, window_label):
    page_base(c, report_name, 1)
    text(c, "R6E8A Pressure Reference Report", 34, H - 67, 24, INK, "Helvetica-Bold")
    text(c, window_label, 34, H - 87, 9.5, MUTED)

    panel(c, 34, H - 245, 344, 132, PANEL_DARK)
    tag(c, "HDF pressure - primary channel", 50, H - 136)
    text(c, "INFRASOUND DETECTED", 50, H - 162, 18, GREEN, "Helvetica-Bold")
    paragraph(c, "Share of current uploaded HDF signal energy inside the ISO 7196 infrasound method band.", 50, H - 185, 205, 9.2, 12, MUTED, max_lines=3)
    text(c, "90%", 358, H - 208, 46, INK, "Helvetica-Bold", "right")

    panel(c, 390, H - 245, 188, 132, CREAM)
    tag(c, "Current recommendation", 406, H - 136, HexColor("#8b5f13"))
    text(c, "TIER 2", 406, H - 166, 24, CREAM_INK, "Helvetica-Bold")
    text(c, "Intermittent", 406, H - 187, 12, CREAM_INK, "Helvetica-Bold")
    paragraph(c, "Highest published-guide index: 172%", 406, H - 207, 156, 9.2, 11, CREAM_INK, "Helvetica-Bold", 2)

    panel(c, 34, H - 289, 544, 31)
    text(c, "100% equals the named guide in threshold panels. ISO shows the recorded-energy share inside its method scope.", 46, H - 278, 8.3, INK, "Helvetica-Bold")

    card_w, card_h = 265, 146
    draw_index_card(c, 34, H - 449, card_w, card_h, "90%", "1 - ISO 7196", "Infrasound method scope", "Recorded-energy share inside the published method band.")
    draw_index_card(c, 313, H - 449, card_w, card_h, "172%", "2 - ANSI/ASA + ASHRAE", "Hotel-room RC screen", "Highest HDF index across instrument-supported RC-30 bands.", True)
    draw_index_card(c, 34, H - 609, card_w, card_h, "46%", "3 - Defra NANR45", "Low-frequency curve", "Highest HDF index across instrument-supported NANR45 bands.")
    draw_index_card(c, 313, H - 609, card_w, card_h, "12%", "4 - WHO + ISO 1996", "Night contribution", "Instrument-supported low-frequency contribution to the bedroom reference.")

    panel(c, 34, 42, 544, 112)
    tag(c, "Current supplied files", 48, 132)
    text(c, "HDF file integrity", 48, 109, 9.5, MUTED)
    text(c, "100%", 244, 109, 12, GREEN, "Helvetica-Bold", "right")
    text(c, "EHZ file integrity", 318, 109, 9.5, MUTED)
    text(c, "100%", 564, 109, 12, BLUE, "Helvetica-Bold", "right")
    text(c, "Highest outside-guide index", 48, 82, 9.5, MUTED)
    text(c, "172%", 244, 82, 12, RED, "Helvetica-Bold", "right")
    text(c, "Verified above-guide share", 318, 82, 9.5, MUTED)
    text(c, "36%", 564, 82, 12, GREEN, "Helvetica-Bold", "right")
    paragraph(c, "HDF supplies every acoustic percentage. EHZ remains an independent vertical-motion record.", 48, 59, 508, 8.4, 10, MUTED, max_lines=2)
    c.showPage()


def draw_trend(c, x, y, width, height):
    panel(c, x, y, width, height, PANEL_DARK)
    tag(c, "S&P-style indexed view", x + 14, y + height - 19)
    text(c, "HDF hotel-room index vs published guide", x + 14, y + height - 39, 12, INK, "Helvetica-Bold")
    left, right, bottom, top = x + 42, x + width - 14, y + 28, y + height - 58
    c.setStrokeColor(HexColor("#1b5543"))
    c.setLineWidth(0.5)
    for pct in (0, 50, 100, 150, 200):
        yy = bottom + (pct / 200) * (top - bottom)
        c.line(left, yy, right, yy)
        text(c, f"{pct}%", left - 6, yy - 2, 6.5, MUTED, "Helvetica", "right")
    guide_y = bottom + 0.5 * (top - bottom)
    c.setStrokeColor(AMBER)
    c.setLineWidth(1.2)
    c.setDash(4, 4)
    c.line(left, guide_y, right, guide_y)
    c.setDash()
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.5)
    path = c.beginPath()
    for idx, value in enumerate(RC_SERIES):
        xx = left + idx * (right - left) / (len(RC_SERIES) - 1)
        yy = bottom + value / 200 * (top - bottom)
        if idx == 0:
            path.moveTo(xx, yy)
        else:
            path.lineTo(xx, yy)
    c.drawPath(path, fill=0, stroke=1)
    text(c, "Aug 3 evening", left, y + 12, 6.8, MUTED)
    text(c, "Midnight", (left + right) / 2, y + 12, 6.8, MUTED, "Helvetica", "center")
    text(c, "Aug 4 - 2:24 AM", right, y + 12, 6.8, MUTED, "Helvetica", "right")


def page_two(c, report_name):
    page_base(c, report_name, 2)
    text(c, "Pressure Index, Tiers and Archive", 34, H - 65, 22, INK, "Helvetica-Bold")
    text(c, "Direct-upload result with fixed outside-guide lines", 34, H - 84, 9.2, MUTED)
    draw_trend(c, 34, H - 350, 544, 242)

    tag(c, "Four-tier action framework", 34, H - 378)
    tier_y, tier_h, gap = H - 493, 96, 8
    tier_w = (544 - gap * 3) / 4
    tier_data = [
        ("TIER 1", "Within guide", "At or below 100%"),
        ("TIER 2", "Intermittent", "Current recommendation"),
        ("TIER 3", "Prolonged", "Elevated follow-up"),
        ("TIER 4", "Extended", "Priority investigation"),
    ]
    for idx, (tier, title_value, copy) in enumerate(tier_data):
        xx = 34 + idx * (tier_w + gap)
        panel(c, xx, tier_y, tier_w, tier_h, HexColor("#07503b") if idx == 1 else PANEL)
        tag(c, tier, xx + 10, tier_y + tier_h - 17)
        text(c, title_value, xx + 10, tier_y + tier_h - 40, 10.2, INK, "Helvetica-Bold")
        paragraph(c, copy, xx + 10, tier_y + tier_h - 57, tier_w - 20, 7.4, 9, GREEN if idx == 1 else MUTED, "Helvetica-Bold" if idx == 1 else "Helvetica", 2)

    panel(c, 34, H - 635, 265, 126)
    tag(c, "Archive scope", 48, H - 532)
    text(c, "April 12, 2026 - Ongoing", 48, H - 554, 13, INK, "Helvetica-Bold")
    paragraph(c, "The original archive scope is preserved. The current four-guide index uses the newest direct HDF upload.", 48, H - 574, 235, 8.5, 11, MUTED, max_lines=4)

    panel(c, 313, H - 635, 265, 126)
    tag(c, "Reading controls", 327, H - 532)
    paragraph(c, "HDF pressure leads. EHZ stays separate. Every percentage uses a named outside guide. Tier 2 includes the manufacturer sensitivity tolerance.", 327, H - 554, 235, 8.5, 11, MUTED, max_lines=5)

    panel(c, 34, 48, 544, 82)
    tag(c, "Source and scope", 48, 108)
    paragraph(c, "*This data may lag. For personal verification, source data can be found through Raspberry Shake FDSN. The displayed percentages index supplied instrument records against published guidance; a complete room evaluation adds complementary full-band instrumentation and site context.", 48, 88, 510, 7.6, 10, MUTED, max_lines=5)
    c.showPage()


def build(filename, report_name, window_label):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / filename
    c = canvas.Canvas(str(target), pagesize=letter, pageCompression=1)
    c.setTitle(report_name)
    c.setAuthor("R6E8A Unit 2709")
    c.setSubject("Percentage-only comparison with four published guidance families")
    page_one(c, report_name, window_label)
    page_two(c, report_name)
    c.save()
    return target


if __name__ == "__main__":
    outputs = [
        build(
            "R6E8A-24-hour-report.pdf",
            "R6E8A 24-Hour Reference Report",
            "Current direct upload through Aug 4, 2026, 2:24 AM Eastern",
        ),
        build(
            "R6E8A-7-day-trailing-report.pdf",
            "R6E8A 7-Day Archive Reference Report",
            "Archive carried forward with the current direct upload indexed",
        ),
    ]
    for output in outputs:
        print(output)
