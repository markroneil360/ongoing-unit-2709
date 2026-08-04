#!/usr/bin/env python3
"""Generate the two public R6E8A PDF reports from derived JSON only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
OUT_DIR = ROOT / "downloads"
GREEN = colors.HexColor("#28d17c")
DEEP_GREEN = colors.HexColor("#063b2d")
INK = colors.HexColor("#13221d")
MUTED = colors.HexColor("#52635d")
LIGHT = colors.HexColor("#edf6f2")
AMBER = colors.HexColor("#f4d88b")
RED = colors.HexColor("#bf2e2e")
LINE = colors.HexColor("#c9d8d1")

# DejaVu renders consistently in browsers and Poppler while keeping the PDFs
# self-contained. ReportLab's built-in Helvetica remains a safe fallback.
DEJAVU_DIR = Path("/usr/share/fonts/truetype/dejavu")
if (DEJAVU_DIR / "DejaVuSans.ttf").exists():
    pdfmetrics.registerFont(TTFont("R6E8A-Regular", DEJAVU_DIR / "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("R6E8A-Bold", DEJAVU_DIR / "DejaVuSans-Bold.ttf"))
    FONT_REGULAR = "R6E8A-Regular"
    FONT_BOLD = "R6E8A-Bold"
else:
    FONT_REGULAR = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def num(value, digits=1):
    if value is None:
        return "N/A"
    return f"{float(value):,.{digits}f}"


def event_from_live(live, channel="HDF", window="trailing_24h_highest"):
    event = live.get("channels", {}).get(channel, {}).get(window)
    if event:
        return event
    if channel == "HDF" and live.get("event_date_et"):
        return {
            "event_date_et": live.get("event_date_et"),
            "display_time_et": live.get("display_time_et"),
            "event_start_utc": live.get("event_start_utc"),
            "event_end_utc": live.get("event_end_utc"),
            "duration_s": live.get("duration_s"),
            "dominant_frequency_hz": live.get("dominant_frequency_hz"),
            "peak_rms_counts": live.get("peak_rms_counts"),
            "window_median_rms_counts": live.get("daily_median_rms_counts"),
            "above_window_median_percent": live.get("above_median_percent"),
            "robust_z": live.get("hdf_robust_z"),
        }
    return None


def styles():
    sheet = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=sheet["Title"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=23,
            textColor=DEEP_GREEN,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=sheet["Normal"],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=sheet["Heading2"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=16,
            textColor=DEEP_GREEN,
            spaceBefore=10,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=sheet["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=sheet["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=7.6,
            leading=10.2,
            textColor=MUTED,
            spaceAfter=5,
        ),
        "callout": ParagraphStyle(
            "Callout",
            parent=sheet["BodyText"],
            fontName=FONT_BOLD,
            fontSize=9,
            leading=13,
            textColor=INK,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=sheet["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=9.5,
            textColor=INK,
        ),
        "cell_bold": ParagraphStyle(
            "CellBold",
            parent=sheet["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            textColor=INK,
        ),
        "cell_header": ParagraphStyle(
            "CellHeader",
            parent=sheet["BodyText"],
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
        ),
    }


def page(canvas, doc):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(DEEP_GREEN)
    canvas.rect(0, height - 0.28 * inch, width, 0.28 * inch, stroke=0, fill=1)
    canvas.setStrokeColor(LINE)
    canvas.line(0.55 * inch, 0.46 * inch, width - 0.55 * inch, 0.46 * inch)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT_REGULAR, 7.5)
    canvas.drawString(0.55 * inch, 0.28 * inch, "R6E8A - Unit 2709 instrument record")
    canvas.drawRightString(width - 0.55 * inch, 0.28 * inch, f"Page {doc.page}")
    canvas.restoreState()


def document(path: Path):
    doc = BaseDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.62 * inch,
        title=path.stem,
        author="Unit 2709 R6E8A Dashboard",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="report", frames=frame, onPage=page))
    return doc


def metric_table(rows, sty):
    data = [[Paragraph("Metric", sty["cell_header"]), Paragraph("Result", sty["cell_header"])]]
    for label, value in rows:
        data.append([Paragraph(str(label), sty["cell"]), Paragraph(str(value), sty["cell_bold"])])
    table = Table(data, colWidths=[2.7 * inch, 3.9 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DEEP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def tier_table(sty):
    rows = [
        ["Tier 1", "Within named reference", "At or below a valid external reference"],
        ["Tier 2", "Intermittent exceedance", "Verified intervals, each under 30 minutes"],
        ["Tier 3", "Prolonged exceedance", "One or more verified intervals of 30-119 minutes"],
        ["Tier 4", "Extended exceedance", "One or more verified intervals of 120 minutes or longer"],
    ]
    data = [[Paragraph("Tier", sty["cell_header"]), Paragraph("Meaning", sty["cell_header"]), Paragraph("Rule", sty["cell_header"])]]
    data += [[Paragraph(cell, sty["cell"]) for cell in row] for row in rows]
    table = Table(data, colWidths=[0.7 * inch, 1.8 * inch, 4.1 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DEEP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [LIGHT, colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def benchmark_table(sty):
    rows = [
        ("ISO 7196", "HDF frequency scope is relevant; calibrated G-weighted dB(G) is not currently computed."),
        ("ANSI/ASA S12.2 and ASHRAE RC/NC", "N/A from raw HDF counts; calibrated octave-band room sound levels are required."),
        ("Defra NANR45", "N/A until calibrated 1/3-octave values from 10-160 Hz are available."),
        ("WHO night noise and ISO 1996", "N/A from HDF/EHZ counts; the required environmental acoustic metrics are not present."),
    ]
    data = [[Paragraph("External reference", sty["cell_header"]), Paragraph("Current comparison status", sty["cell_header"])]]
    data += [[Paragraph(a, sty["cell_bold"]), Paragraph(b, sty["cell"])] for a, b in rows]
    table = Table(data, colWidths=[2.15 * inch, 4.45 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DEEP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def report_header(story, sty, title, subtitle):
    story.append(Paragraph(title, sty["title"]))
    story.append(Paragraph(subtitle, sty["subtitle"]))
    note = Table(
        [[Paragraph("* Account for up to 30 minutes of source-archive lag.", sty["callout"]) ]],
        colWidths=[6.6 * inch],
    )
    note.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), AMBER),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#a77910")),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([note, Spacer(1, 8)])


def build_24h(live, history, path):
    sty = styles()
    doc = document(path)
    story = []
    cutoff = live.get("analyzed_through_et", "latest available FDSN cutoff")
    report_header(
        story,
        sty,
        "R6E8A 24-Hour Instrument Report",
        f"Unit 2709 | April 12, 2026 - Ongoing | Analyzed through {cutoff}",
    )

    hdf = event_from_live(live, "HDF")
    ehz = event_from_live(live, "EHZ")
    story.append(Paragraph("Quick summary", sty["h2"]))
    if hdf:
        story.append(
            Paragraph(
                "The highest HDF one-second RMS event in the available trailing window occurred at "
                f"<b>{hdf.get('display_time_et', 'N/A')}</b>. HDF is the primary pressure/infrasound "
                "channel. EHZ is reported separately as vertical-motion context; the two channels are "
                "not combined and the record does not identify a source.",
                sty["body"],
            )
        )
    else:
        story.append(Paragraph("No current HDF event summary was available. Values remain N/A.", sty["body"]))

    story.append(Paragraph("HDF pressure/infrasound - trailing window", sty["h2"]))
    story.append(
        metric_table(
            [
                ("Highest event time", hdf.get("display_time_et", "N/A") if hdf else "N/A"),
                ("Event duration", f"{num(hdf.get('duration_s'), 2)} seconds" if hdf else "N/A"),
                ("Dominant frequency", f"{num(hdf.get('dominant_frequency_hz'), 4)} Hz" if hdf else "N/A"),
                ("Peak one-second RMS", f"{num(hdf.get('peak_rms_counts'), 1)} instrument counts" if hdf else "N/A"),
                ("Window median RMS", f"{num(hdf.get('window_median_rms_counts'), 1)} instrument counts" if hdf else "N/A"),
                ("Difference from same-channel window median", f"{num(hdf.get('above_window_median_percent'), 1)}%" if hdf else "N/A"),
            ],
            sty,
        )
    )
    story.append(
        Paragraph(
            "The percentage above the HDF window median is descriptive same-channel context only. "
            "It is not an external-standard exceedance or a distribution-rank statistic.",
            sty["small"],
        )
    )

    story.append(Paragraph("EHZ vertical motion - separate channel", sty["h2"]))
    story.append(
        metric_table(
            [
                ("Highest event time", ehz.get("display_time_et", "N/A") if ehz else "N/A"),
                ("Event duration", f"{num(ehz.get('duration_s'), 2)} seconds" if ehz else "N/A"),
                ("Dominant frequency", f"{num(ehz.get('dominant_frequency_hz'), 4)} Hz" if ehz else "N/A"),
                ("Peak one-second RMS", f"{num(ehz.get('peak_rms_counts'), 1)} instrument counts" if ehz else "N/A"),
            ],
            sty,
        )
    )
    story.append(PageBreak())
    story.append(Paragraph("Four-tier monitoring framework", sty["h2"]))
    story.append(tier_table(sty))
    story.append(
        Paragraph(
            "No tier is assigned from raw instrument counts. Tier assignment requires a valid named "
            "external reference and the matching calibrated metric, weighting and averaging window.",
            sty["small"],
        )
    )
    story.append(Paragraph("External reference status", sty["h2"]))
    story.append(benchmark_table(sty))
    story.append(Paragraph("Sources and methods", sty["h2"]))
    story.append(
        Paragraph(
            "Source: Raspberry Shake FDSN DataSelect for station AM.R6E8A. Official channel views: "
            '<link href="https://dataview.raspberryshake.org/#/embed/AM/R6E8A/00/HDF">HDF DataView</link> and '
            '<link href="https://dataview.raspberryshake.org/#/embed/AM/R6E8A/00/EHZ">EHZ DataView</link>. '
            "Processing uses one-second RMS instrument counts with no interpolation across gaps. Missing "
            "samples remain unavailable and are never set to zero.",
            sty["body"],
        )
    )
    story.append(
        Paragraph(
            "*This Data may lag. For personal verification, data can be found at "
            '<link href="https://data.raspberryshake.org/fdsnws/">Raspberry Shake FDSN</link>.',
            sty["small"],
        )
    )
    doc.build(story)


def build_7d(live, history, path):
    sty = styles()
    doc = document(path)
    story = []
    days = sorted(history.get("days", []), key=lambda item: item.get("event_date_et", ""))[-7:]
    start_label = days[0].get("event_date_et", "N/A") if days else "N/A"
    end_label = days[-1].get("event_date_et", "N/A") if days else "N/A"
    report_header(
        story,
        sty,
        "R6E8A Trailing 7-Day Instrument Report",
        f"Unit 2709 | {start_label} through {end_label} | HDF and EHZ kept separate",
    )
    story.append(Paragraph("Daily HDF highest-event record", sty["h2"]))
    headers = ["Date", "Time EST", "Dur.", "Freq.", "Peak RMS", "% above median", "EHZ z"]
    data = [[Paragraph(item, sty["cell_header"]) for item in headers]]
    for item in days:
        time_label = item.get("display_time_et", "N/A").split(" - ")[-1]
        data.append(
            [
                Paragraph(item.get("event_date_et", "N/A"), sty["cell"]),
                Paragraph(time_label, sty["cell"]),
                Paragraph(f"{num(item.get('duration_s'), 1)} s", sty["cell"]),
                Paragraph(f"{num(item.get('dominant_frequency_hz'), 3)} Hz", sty["cell"]),
                Paragraph(num(item.get("peak_rms_counts"), 0), sty["cell"]),
                Paragraph(f"{num(item.get('above_median_percent'), 1)}%", sty["cell"]),
                Paragraph(num(item.get("simultaneous_ehz_robust_z"), 2), sty["cell"]),
            ]
        )
    table = Table(
        data,
        colWidths=[0.82 * inch, 1.02 * inch, 0.48 * inch, 0.65 * inch, 0.82 * inch, 1.0 * inch, 0.55 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DEEP_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(
        Paragraph(
            "Daily percentage values are same-HDF-channel descriptive comparisons to each day's median. "
            "They are not distribution-rank statistics and are not external-standard exceedances.",
            sty["small"],
        )
    )

    if days:
        peak_day = max(days, key=lambda item: float(item.get("peak_rms_counts") or -1))
        relative_day = max(days, key=lambda item: float(item.get("above_median_percent") or -1))
        story.append(Paragraph("Seven-day instrument summary", sty["h2"]))
        story.append(
            metric_table(
                [
                    ("Highest HDF peak RMS day", f"{peak_day.get('event_date_et')} - {num(peak_day.get('peak_rms_counts'), 1)} counts"),
                    ("Largest same-day relative difference", f"{relative_day.get('event_date_et')} - {num(relative_day.get('above_median_percent'), 1)}% above median"),
                    ("Documented days in this report", str(len(days))),
                    ("Channel handling", "HDF primary; EHZ independent vertical-motion context"),
                ],
                sty,
            )
        )

    reference = history.get("archived_reference")
    if reference:
        story.append(Paragraph("August 3 early-morning archived detector reference", sty["h2"]))
        callout = Table(
            [[Paragraph(
                f"{reference.get('display_time_et', 'N/A')}: {num(reference.get('duration_s'), 1)} s, "
                f"{num(reference.get('dominant_frequency_hz'), 4)} Hz, "
                f"{num(reference.get('peak_rms_counts'), 1)} HDF RMS counts, "
                f"{num(reference.get('above_median_percent'), 1)}% above the then-current HDF median. "
                "This preserved detector record is not a complete 2:30-3:00 AM interval analysis.",
                sty["body"],
            )]],
            colWidths=[6.6 * inch],
        )
        callout.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.7, GREEN),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(callout)

    story.append(PageBreak())
    story.append(Paragraph("Four-tier monitoring framework", sty["h2"]))
    story.append(tier_table(sty))
    story.append(
        Paragraph(
            "No tier is assigned from the raw-count table above. A tier requires the matching calibrated "
            "external-reference metric and a verified continuous duration.",
            sty["small"],
        )
    )
    story.append(Paragraph("External reference status", sty["h2"]))
    story.append(benchmark_table(sty))
    story.append(Paragraph("Sources and methods", sty["h2"]))
    story.append(
        Paragraph(
            "Source: Raspberry Shake FDSN DataSelect and the repository's preserved hourly derived records. "
            "Raw MiniSEED is not redistributed. HDF and EHZ are evaluated independently. Missing samples "
            "remain unavailable and are never treated as zero. Official verification: "
            '<link href="https://data.raspberryshake.org/fdsnws/">Raspberry Shake FDSN</link>.',
            sty["body"],
        )
    )
    story.append(
        Paragraph(
            "*This Data may lag. Account for up to 30 minutes of source-archive lag.",
            sty["small"],
        )
    )
    doc.build(story)


def main():
    live = load_json(LIVE_PATH)
    history = load_json(HISTORY_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    build_24h(live, history, OUT_DIR / "R6E8A-24-hour-report.pdf")
    build_7d(live, history, OUT_DIR / "R6E8A-7-day-trailing-report.pdf")
    print("Generated", OUT_DIR / "R6E8A-24-hour-report.pdf")
    print("Generated", OUT_DIR / "R6E8A-7-day-trailing-report.pdf")


if __name__ == "__main__":
    main()
