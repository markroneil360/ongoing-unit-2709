#!/usr/bin/env python3
"""Create the R6E8A 24-hour and trailing-seven-day public PDF reports.

The reports show HDF pressure first, keep EHZ separate, and compare R6E8A only
with the four named external guidance families. Detector medians and other
same-station baselines are intentionally excluded from every public page.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
LIVE_PATH = ROOT / "data" / "daily-highest.json"
HISTORY_PATH = ROOT / "data" / "daily-highest-history.json"
ARCHIVE_PATH = ROOT / "data" / "unified_daily.json"
OUT_24H = ROOT / "downloads" / "R6E8A-24-hour-report.pdf"
OUT_7D = ROOT / "downloads" / "R6E8A-7-day-trailing-report.pdf"
HDF_COUNTS_PER_PA = 56_000.0
FONT_REGULAR = "R6E8A-DejaVu"
FONT_BOLD = "R6E8A-DejaVu-Bold"
pdfmetrics.registerFont(TTFont(FONT_REGULAR, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont(FONT_BOLD, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

DEEP = colors.HexColor("#06110D")
GREEN = colors.HexColor("#159957")
GREEN_LIGHT = colors.HexColor("#DDF7E9")
BLUE_LIGHT = colors.HexColor("#E6F3FF")
AMBER_LIGHT = colors.HexColor("#FFF3D2")
RED_LIGHT = colors.HexColor("#FFE8E9")
INK = colors.HexColor("#102019")
MUTED = colors.HexColor("#5D7067")
LINE = colors.HexColor("#B8CEC3")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value) -> str:
    return html.escape("N/A" if value is None else str(value))


def num(value, digits=1) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def pressure_pa(event: dict | None) -> float | None:
    if not event:
        return None
    value = event.get("estimated_pressure_pa_rms_nominal")
    if value is not None:
        return float(value)
    counts = event.get("peak_rms_counts")
    return float(counts) / HDF_COUNTS_PER_PA if counts is not None else None


def pressure_label(event: dict | None) -> str:
    value = pressure_pa(event)
    if value is None:
        return "N/A"
    digits = 2 if value >= 1 else 3 if value >= 0.1 else 4
    return f"approximately {value:,.{digits}f} Pa RMS*"


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title", parent=base["Title"], fontName=FONT_BOLD, fontSize=22,
            leading=24, textColor=colors.white, alignment=TA_LEFT, spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["BodyText"], fontName=FONT_REGULAR, fontSize=8.5,
            leading=11, textColor=colors.HexColor("#CFE5D9"), spaceAfter=0,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName=FONT_BOLD, fontSize=15,
            leading=18, textColor=DEEP, spaceBefore=4, spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName=FONT_BOLD, fontSize=11,
            leading=13, textColor=GREEN, spaceBefore=4, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName=FONT_REGULAR, fontSize=8.4,
            leading=11.2, textColor=INK, spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName=FONT_REGULAR, fontSize=7.1,
            leading=9.1, textColor=MUTED, spaceAfter=3,
        ),
        "card_label": ParagraphStyle(
            "CardLabel", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=6.8,
            leading=8, textColor=MUTED, spaceAfter=3,
        ),
        "card_value": ParagraphStyle(
            "CardValue", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=11,
            leading=13, textColor=DEEP, spaceAfter=2,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=6.6,
            leading=8, textColor=colors.white,
        ),
        "table": ParagraphStyle(
            "Table", parent=base["BodyText"], fontName=FONT_REGULAR, fontSize=6.7,
            leading=8.4, textColor=INK,
        ),
        "table_bold": ParagraphStyle(
            "TableBold", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=6.7,
            leading=8.4, textColor=INK,
        ),
        "center": ParagraphStyle(
            "Center", parent=base["BodyText"], fontName=FONT_BOLD, fontSize=8.2,
            leading=10, textColor=INK, alignment=TA_CENTER,
        ),
    }


def page_template(canvas, doc):
    width, height = letter
    canvas.saveState()
    canvas.setFillColor(DEEP)
    canvas.rect(0, height - 0.63 * inch, width, 0.63 * inch, fill=1, stroke=0)
    canvas.setStrokeColor(GREEN)
    canvas.setLineWidth(2)
    canvas.line(0.48 * inch, 0.43 * inch, width - 0.48 * inch, 0.43 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT_REGULAR, 7)
    canvas.drawString(0.5 * inch, 0.25 * inch, "R6E8A · April 12, 2026 - Ongoing · Eastern Time")
    canvas.drawRightString(width - 0.5 * inch, 0.25 * inch, f"Page {doc.page}")
    canvas.restoreState()


def header_block(sty, title: str, subtitle: str):
    table = Table(
        [[Paragraph(title, sty["title"]), Paragraph(subtitle, sty["subtitle"])]] ,
        colWidths=[4.9 * inch, 2.0 * inch],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DEEP),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("BOX", (0, 0), (-1, -1), 0.5, GREEN),
    ]))
    return table


def summary_cards(sty, live: dict):
    hdf = ((live.get("channels") or {}).get("HDF") or {}).get("detroit_day_highest") or live
    ehz = ((live.get("channels") or {}).get("EHZ") or {}).get("detroit_day_highest") or {}
    cards = [
        ("LATEST DUAL-CHANNEL CUTOFF", live.get("analyzed_through_et", "N/A"), "Latest processed point available from both channels."),
        ("HDF PRESSURE LEADS", pressure_label(hdf), "Nominal one-second estimate; not a handbook grade."),
        ("PRESSURE EVENT", hdf.get("display_time_et", "N/A"), f"{num(hdf.get('dominant_frequency_hz'), 4)} Hz · {num(hdf.get('duration_s'), 1)} sec detector window"),
        ("EXTERNAL GUIDE RESULT", "Not yet gradeable", "No percentage or tier until the same required metric is measured."),
    ]
    cells = []
    for label, value, note in cards:
        cells.append([
            Paragraph(label, sty["card_label"]),
            Paragraph(esc(value), sty["card_value"]),
            Paragraph(esc(note), sty["small"]),
        ])
    table = Table([cells], colWidths=[1.72 * inch] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def benchmark_table(sty):
    rows = [
        [
            Paragraph("PUBLISHED GUIDE", sty["table_head"]),
            Paragraph("OUTSIDE REFERENCE", sty["table_head"]),
            Paragraph("R6E8A RESULT", sty["table_head"]),
            Paragraph("WHY", sty["table_head"]),
        ],
        [
            Paragraph("1 · ISO 7196<br/><font color='#159957'>Infrasound pressure</font>", sty["table_bold"]),
            Paragraph("G-weighted pressure for 1-20 Hz. It is a measurement method and sets no danger limit.", sty["table"]),
            Paragraph("N/A · dB(G) not yet computed", sty["table_bold"]),
            Paragraph("Needs station-response correction to Pa and validated G weighting.", sty["table"]),
        ],
        [
            Paragraph("2 · ANSI/ASA + ASHRAE<br/><font color='#159957'>Hotel room</font>", sty["table_bold"]),
            Paragraph("Hotel room/suite target NC/RC 30; approximately 35 dBA and 60 dBC. Project target may vary ±5.", sty["table"]),
            Paragraph("N/A · NC/RC not measured", sty["table_bold"]),
            Paragraph("Needs a calibrated room survey with the required octave bands and positions.", sty["table"]),
        ],
        [
            Paragraph("3 · Defra NANR45<br/><font color='#159957'>Low frequency</font>", sty["table_bold"]),
            Paragraph("Indoor five-minute 1/3-octave night curve: 92 to 34 dB across 10-160 Hz.", sty["table"]),
            Paragraph("N/A · full band set unavailable", sty["table_bold"]),
            Paragraph("R6E8A cannot supply the required 50-160 Hz bands or full indoor procedure.", sty["table"]),
        ],
        [
            Paragraph("4 · WHO + ISO 1996<br/><font color='#159957'>Night environment</font>", sty["table_bold"]),
            Paragraph("30 dBA bedroom overnight; 40 dBA annual outside guideline; 55 dBA annual interim target.", sty["table"]),
            Paragraph("N/A · dBA averages not measured", sty["table_bold"]),
            Paragraph("Needs calibrated A-weighted sound and each guide’s location and averaging period.", sty["table"]),
        ],
    ]
    table = Table(rows, colWidths=[1.25 * inch, 2.15 * inch, 1.45 * inch, 2.05 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DEEP),
        ("BACKGROUND", (0, 1), (-1, 1), GREEN_LIGHT),
        ("BACKGROUND", (0, 2), (-1, 2), BLUE_LIGHT),
        ("BACKGROUND", (0, 3), (-1, 3), AMBER_LIGHT),
        ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#F1EAFF")),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def channel_details(sty, live: dict):
    channels = live.get("channels") or {}
    hdf_channel = channels.get("HDF") or {}
    ehz_channel = channels.get("EHZ") or {}
    hdf = hdf_channel.get("detroit_day_highest") or live
    ehz = ehz_channel.get("detroit_day_highest") or {}
    hdf_rows = [
        [Paragraph("HDF · AIR PRESSURE", sty["table_head"]), ""],
        [Paragraph("Availability", sty["table"]), Paragraph("Available" if hdf_channel.get("available") else "N/A", sty["table_bold"])],
        [Paragraph("Highest detector event", sty["table"]), Paragraph(esc(hdf.get("display_time_et")), sty["table_bold"])],
        [Paragraph("Nominal pressure", sty["table"]), Paragraph(esc(pressure_label(hdf)), sty["table_bold"])],
        [Paragraph("Dominant frequency", sty["table"]), Paragraph(f"{num(hdf.get('dominant_frequency_hz'), 4)} Hz", sty["table_bold"])],
        [Paragraph("Detector window", sty["table"]), Paragraph(f"{num(hdf.get('duration_s'), 1)} seconds", sty["table_bold"])],
        [Paragraph("Outside-guide result", sty["table"]), Paragraph("N/A · unmatched metric", sty["table_bold"])],
    ]
    ehz_rows = [
        [Paragraph("EHZ · VERTICAL MOTION", sty["table_head"]), ""],
        [Paragraph("Availability", sty["table"]), Paragraph("Available" if ehz_channel.get("available") else "N/A", sty["table_bold"])],
        [Paragraph("Highest detector event", sty["table"]), Paragraph(esc(ehz.get("display_time_et")), sty["table_bold"])],
        [Paragraph("Instrument reading", sty["table"]), Paragraph(f"{num(ehz.get('peak_rms_counts'), 1)} counts", sty["table_bold"])],
        [Paragraph("Dominant frequency", sty["table"]), Paragraph(f"{num(ehz.get('dominant_frequency_hz'), 4)} Hz", sty["table_bold"])],
        [Paragraph("Detector window", sty["table"]), Paragraph(f"{num(ehz.get('duration_s'), 1)} seconds", sty["table_bold"])],
        [Paragraph("Acoustic guides", sty["table"]), Paragraph("Not applicable to EHZ", sty["table_bold"])],
    ]
    def make(rows, accent):
        t = Table(rows, colWidths=[1.45 * inch, 1.95 * inch])
        t.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (1, 0), accent),
            ("GRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t
    return Table([[make(hdf_rows, GREEN), make(ehz_rows, colors.HexColor("#3A82B7"))]], colWidths=[3.45 * inch, 3.45 * inch], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])


def history_table(sty, history: dict, limit: int):
    days = sorted(history.get("days") or [], key=lambda item: str(item.get("event_date_et", "")))[-limit:]
    rows = [[Paragraph(value, sty["table_head"]) for value in ("DATE", "HDF EVENT", "NOMINAL PA RMS*", "FREQUENCY", "DETECTOR WINDOW", "OUTSIDE GUIDE")]]
    for item in days:
        rows.append([
            Paragraph(esc(item.get("event_date_et")), sty["table"]),
            Paragraph(esc(item.get("display_time_et")), sty["table"]),
            Paragraph(esc(pressure_label(item)), sty["table_bold"]),
            Paragraph(f"{num(item.get('dominant_frequency_hz'), 4)} Hz", sty["table"]),
            Paragraph(f"{num(item.get('duration_s'), 1)} sec", sty["table"]),
            Paragraph("N/A", sty["table_bold"]),
        ])
    if len(rows) == 1:
        rows.append([Paragraph("No preserved recent history available", sty["table"]), "", "", "", "", ""])
    table = Table(rows, colWidths=[0.78 * inch, 1.55 * inch, 1.15 * inch, 0.9 * inch, 1.05 * inch, 1.25 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DEEP), ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def tier_table(sty):
    rows = [
        ["TIER 1", "TIER 2", "TIER 3", "TIER 4"],
        ["Within named guide", "Intermittent exceedance", "Prolonged exceedance", "Extended exceedance"],
        ["Matched result at/below guide", "Each interval under 30 min", "30-119 continuous min", "120+ continuous min"],
    ]
    data = [[Paragraph(cell, sty["center"] if row else sty["table_head"]) for cell in line] for row, line in enumerate(rows)]
    table = Table(data, colWidths=[1.72 * inch] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), GREEN), ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#C89A16")),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#D56A2E")), ("BACKGROUND", (3, 0), (3, 0), colors.HexColor("#D34249")),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def footer_text(sty):
    return [
        Paragraph("Reading controls", sty["h2"]),
        Paragraph(
            "HDF is air pressure; EHZ is vertical motion; their amplitudes are never combined. "
            "Detector windows locate events, not time above a guide. Missing samples remain N/A.",
            sty["body"],
        ),
        Paragraph(
            "*Nominal Pa = one-second HDF RMS counts ÷ 56,000 (manufacturer estimate, ±10%); response-uncorrected and unweighted; not a guide or safety grade.",
            sty["small"],
        ),
        Paragraph(
            "<b>*Account for up to 30 minutes of lag.</b> For personal verification, use the "
            "<link href='https://data.raspberryshake.org/fdsnws/'>Raspberry Shake source service</link>. "
            "This report documents instrument records and published-guide readiness; it does not identify a source, cause, person, medical effect or safety condition.",
            sty["small"],
        ),
    ]


def build(path: Path, title: str, window_label: str, live: dict, history: dict):
    sty = styles()
    doc = BaseDocTemplate(
        str(path), pagesize=letter, rightMargin=0.5 * inch, leftMargin=0.5 * inch,
        topMargin=0.78 * inch, bottomMargin=0.55 * inch,
        title=title, author="R6E8A Unit 2709",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=page_template))
    story = [
        header_block(sty, title, f"{window_label}<br/>Pressure first · EHZ separate · outside guides only"),
        Spacer(1, 0.12 * inch),
        summary_cards(sty, live),
        Spacer(1, 0.1 * inch),
        Paragraph("Plain-language bottom line", sty["h2"]),
        Table([[Paragraph(
            "<b>Pressure activity is present in the HDF record.</b> The current feed supports a nominal pressure estimate, "
            "but not a truthful percent-above, danger label, pass/fail result or monitoring tier under the four published guides.",
            sty["body"],
        )]], colWidths=[6.88 * inch], style=[("BACKGROUND", (0, 0), (-1, -1), GREEN_LIGHT), ("BOX", (0, 0), (-1, -1), 0.6, GREEN), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]),
        Spacer(1, 0.08 * inch),
        Paragraph("Four published-guide comparison board", sty["h1"]),
        Paragraph("Each row keeps the guide’s own units and duration. No same-station or peer-station baseline is used.", sty["body"]),
        benchmark_table(sty),
        PageBreak(),
        Spacer(1, 0.16 * inch),
        header_block(sty, "R6E8A event record", "HDF pressure leads<br/>EHZ motion remains separate"),
        Spacer(1, 0.12 * inch),
        channel_details(sty, live),
        Spacer(1, 0.12 * inch),
        Paragraph("Preserved recent HDF pressure events", sty["h1"]),
        history_table(sty, history, 1 if "24-Hour" in title else 7),
        Spacer(1, 0.1 * inch),
        Paragraph("Monitoring-priority framework", sty["h1"]),
        tier_table(sty),
        Paragraph("Current tier: N/A. A detector window is not an outside-guide exceedance interval.", sty["small"]),
        Spacer(1, 0.05 * inch),
        *footer_text(sty),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story)


def main():
    live = load(LIVE_PATH)
    history = load(HISTORY_PATH)
    build(OUT_24H, "R6E8A 24-Hour Pressure Report", "Latest processed 24-hour window", live, history)
    build(OUT_7D, "R6E8A Trailing 7-Day Report", "Preserved recent daily detector record", live, history)
    print(f"Wrote {OUT_24H}")
    print(f"Wrote {OUT_7D}")


if __name__ == "__main__":
    main()
