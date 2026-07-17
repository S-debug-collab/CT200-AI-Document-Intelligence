
import argparse
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans-BoldOblique", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"))

STYLES = {
    "title": ParagraphStyle("title", fontName="DejaVuSans-Bold", fontSize=20, leading=24, spaceAfter=14),
    "h1": ParagraphStyle("h1", fontName="DejaVuSans-Bold", fontSize=16, leading=20, spaceBefore=14, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="DejaVuSans-Bold", fontSize=13, leading=17, spaceBefore=10, spaceAfter=6, leftIndent=0),
    "h3": ParagraphStyle("h3", fontName="DejaVuSans-Bold", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=5, leftIndent=8),
    "h4": ParagraphStyle("h4", fontName="DejaVuSans-BoldOblique", fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=4, leftIndent=16),
    "body": ParagraphStyle("body", fontName="DejaVuSans", fontSize=10, leading=14, spaceAfter=6),
    "listitem": ParagraphStyle("listitem", fontName="DejaVuSans", fontSize=10, leading=14, leftIndent=18, spaceAfter=2),
}


def P(kind, text):
    return ("para", kind, text)


def T(rows):
    return ("table", None, rows)


def build_blocks(version):
    b = []
    b.append(P("title", "CardioTrack CT-200 Home Blood Pressure Monitor &mdash; Technical &amp; User Manual"))

    b.append(P("h1", "1. Device Overview"))
    b.append(P("body", "The CardioTrack CT-200 is an oscillometric, upper-arm blood pressure monitor intended for "
                        "home use by adult users. It measures systolic pressure, diastolic pressure, and pulse "
                        "rate, and stores up to 200 readings across two user profiles."))
    b.append(P("h2", "1.1 Intended Use"))
    b.append(P("body", "The CT-200 is intended to non-invasively measure blood pressure and pulse rate in adults "
                        "with an arm circumference of 22&ndash;42 cm. It is not intended for use on neonates, "
                        "infants, or pregnant users, and is not a diagnostic device &mdash; readings should be "
                        "interpreted by a qualified clinician."))
    b.append(P("h2", "1.2 Indications and Contraindications"))
    b.append(P("body", "The device should not be used on the arm ipsilateral to a mastectomy, on limbs with an "
                        "active intravenous line, or on users with severe arrhythmia without clinician guidance, "
                        "since oscillometric measurement can be unreliable in these cases."))

    b.append(P("h1", "2. Physical and Electrical Specifications"))
    b.append(P("h2", "2.1 General Specifications"))
    b.append(T([
        ["Parameter", "Value"],
        ["Measurement method", "Oscillometric"],
        ["Pressure range", "0-299 mmHg"],
        ["Pulse range", "40-199 bpm"],
        ["Accuracy (pressure)", "\u00b13 mmHg"],
        ["Accuracy (pulse)", "\u00b15%"],
        ["Power source", "4x AA batteries or 6V DC adapter"],
        ["Display", "Backlit LCD"],
    ]))
    b.append(P("h4", "2.1.1.1 Battery Life Under Typical Use"))
    if version == 1:
        b.append(P("body", "Under typical use (three measurements per day), four AA alkaline batteries provide "
                            "approximately 300 measurement cycles before requiring replacement. The device "
                            "displays a low-battery icon once remaining capacity falls below 15%."))
    else:
        b.append(P("body", "Under typical use (three measurements per day), four AA alkaline batteries provide "
                            "approximately 250 measurement cycles before requiring replacement &mdash; revised "
                            "downward from earlier estimates after extended field testing. The device displays a "
                            "low-battery icon once remaining capacity falls below 10%."))
    b.append(P("h2", "2.2 Cuff Specifications"))
    b.append(P("body", "The standard cuff supplied with the CT-200 fits arm circumferences of 22&ndash;32 cm. A "
                        "separate large cuff (part number CT200-LC) is available for 32&ndash;42 cm and must be "
                        "ordered separately; using the standard cuff outside its rated range will produce "
                        "inaccurate readings."))

    b.append(P("h1", "3. Device Operation"))
    b.append(P("h2", "3.1 Powering On and Profile Selection"))
    b.append(P("body", "Press and hold the power button for one second to power on the device. Use the profile "
                        "button to select User 1 or User 2 before beginning a measurement; readings are stored "
                        "against whichever profile is active at the time of measurement."))
    b.append(P("h2", "3.2 Cuff Inflation Sequence"))
    if version == 1:
        b.append(P("body", "On starting a measurement, the device inflates the cuff to an initial target of 180 "
                            "mmHg. If the user's pulse is not detected by 180 mmHg, the device inflates in 40 mmHg "
                            "increments up to a maximum of 299 mmHg before aborting with an error. Deflation "
                            "occurs in controlled steps of approximately 3 mmHg to capture oscillometric pulse "
                            "data."))
    else:
        b.append(P("body", "On starting a measurement, the device inflates the cuff to an initial target of 180 "
                            "mmHg. If the user's pulse is not detected by 180 mmHg, the device inflates in 30 mmHg "
                            "increments up to a maximum of 299 mmHg before aborting with an error. Deflation "
                            "occurs in controlled steps of approximately 3 mmHg to capture oscillometric pulse "
                            "data. Increment size was reduced from the original 40 mmHg to improve pulse-detection "
                            "reliability in field testing."))
    # NOTE: 3.4 appears BEFORE 3.3 in physical document order -- intentional irregularity.
    b.append(P("h2", "3.4 Auto Shutoff"))
    b.append(P("body", "To conserve battery, the CT-200 automatically powers off after 60 seconds of inactivity "
                        "on the home screen, and after 3 minutes of inactivity if a measurement screen is left "
                        "open without starting a reading."))
    b.append(P("h2", "3.3 Result Display and Classification"))
    b.append(P("body", "After a completed measurement, the device displays systolic pressure, diastolic pressure, "
                        "and pulse rate simultaneously, along with a classification indicator (see 2.1, 4.3 for "
                        "related specifications and alarm thresholds) based on the most recent joint clinical "
                        "guidance available at time of manufacture."))
    # Numbered list that DELIBERATELY collides with top-level section numbers 1-5.
    b.append(P("listitem", "1. Normal: systolic &lt; 120 and diastolic &lt; 80"))
    b.append(P("listitem", "2. Elevated: systolic 120&ndash;129 and diastolic &lt; 80"))
    b.append(P("listitem", "3. Hypertension Stage 1: systolic 130&ndash;139 or diastolic 80&ndash;89"))
    b.append(P("listitem", "4. Hypertension Stage 2: systolic &#8805; 140 or diastolic &#8805; 90"))
    b.append(P("listitem", "5. Hypertensive Crisis: systolic &gt; 180 or diastolic &gt; 120 &mdash; device "
                            "recommends seeking immediate medical attention"))

    b.append(P("h1", "4. Alarms and Safety Behavior"))
    b.append(P("h2", "4.1 Overpressure Protection"))
    b.append(P("body", "If cuff pressure exceeds 299 mmHg at any point, or exceeds 300 mmHg for longer than 3 "
                        "seconds due to sensor fault, the device immediately triggers an emergency deflation "
                        "valve, halting inflation and venting the cuff within 2 seconds, independent of the main "
                        "firmware control loop."))
    b.append(P("h2", "4.2 Error Codes"))
    if version == 1:
        rows = [
            ["Code", "Meaning", "Device Behavior"],
            ["E1", "Cuff not connected or leak detected", "Aborts measurement, displays E1"],
            ["E2", "Motion artifact detected during measurement", "Aborts measurement, displays E2, prompts retry"],
            ["E3", "Overpressure condition", "Auto-deflates within 2 seconds, displays E3"],
            ["E4", "Low battery during measurement", "Aborts measurement, displays E4"],
            ["E5", "Internal sensor fault", "Device disables measurement function, displays E5 until serviced"],
        ]
    else:
        rows = [
            ["Code", "Meaning", "Device Behavior"],
            ["E1", "Cuff not connected or leak detected", "Aborts measurement, displays E1"],
            ["E2", "Motion artifact detected during measurement", "Aborts measurement, displays E2, prompts retry"],
            ["E3", "Overpressure condition", "Auto-deflates within 1.5 seconds, displays E3"],
            ["E4", "Low battery during measurement", "Aborts measurement, displays E4"],
            ["E5", "Internal sensor fault", "Device disables measurement function, displays E5 until serviced"],
            ["E6", "Bluetooth sync failure", "Displays E6 on next sync attempt; does not affect measurement"],
        ]
    b.append(T(rows))
    b.append(P("h2", "4.3 Alarm Thresholds"))
    if version == 1:
        b.append(P("body", "The device does not sound an audible alarm for elevated readings by default; audible "
                            "alarms are limited to the E1&ndash;E5 error conditions above and are user-configurable "
                            "in the settings menu, except for E3 (overpressure), which cannot be silenced for "
                            "safety reasons."))
    else:
        b.append(P("body", "The device does not sound an audible alarm for elevated readings by default; audible "
                            "alarms are limited to the E1&ndash;E6 error conditions above and are user-configurable "
                            "in the settings menu, except for E3 (overpressure), which cannot be silenced for "
                            "safety reasons."))

    b.append(P("h1", "5. Data Management"))
    b.append(P("h2", "5.1 Local Storage"))
    b.append(P("body", "The CT-200 stores up to 100 readings per user profile in non-volatile memory. When "
                        "storage is full, the oldest reading for that profile is overwritten automatically; there "
                        "is no user-facing warning before this occurs."))
    b.append(P("h2", "5.2 Bluetooth Sync"))
    b.append(P("body", "The device can pair with the CardioTrack companion app via Bluetooth Low Energy. Readings "
                        "sync automatically when the app is open and the device is within range; there is no "
                        "manual \"sync now\" trigger in firmware version 1.x."))
    if version == 2:
        b.append(P("h2", "5.3 Data Export"))
        b.append(P("body", "Starting with firmware 1.4, the companion app supports exporting stored readings as "
                            "a CSV file containing timestamp, profile, systolic, diastolic, pulse, and "
                            "classification columns. Export requires the device to have completed at least one "
                            "successful Bluetooth sync in the current session."))

    b.append(P("h1", "6. Maintenance and Cleaning"))
    b.append(P("h2", "6.1 Cleaning Instructions"))
    b.append(P("body", "Wipe the device body and cuff exterior with a soft, dry cloth or one lightly dampened "
                        "with water. Do not submerge the device or cuff, and do not use alcohol, solvents, or "
                        "abrasive cleaners on the display."))
    b.append(P("h2", "6.2 Calibration"))
    b.append(P("body", "Anthropic recommends professional recalibration every 2 years or after any drop or "
                        "significant impact. The device does not perform self-calibration; there is no field "
                        "calibration procedure available to end users."))

    b.append(P("h1", "7. Troubleshooting"))
    b.append(P("h2", "7.1 Error Codes"))
    b.append(P("body", "If a code from Section 4.2 appears and persists after following the on-screen retry "
                        "prompt twice, users should discontinue use and contact CardioTrack support rather than "
                        "attempting further self-diagnosis, particularly for E5, which indicates an internal "
                        "sensor fault."))
    b.append(P("h2", "7.2 Inconsistent Readings"))
    b.append(P("body", "Inconsistent readings between measurements are most commonly caused by cuff "
                        "mispositioning, talking or moving during measurement, or measuring within 30 minutes of "
                        "exercise, caffeine, or smoking; the manual recommends resting quietly for 5 minutes "
                        "before remeasuring."))

    b.append(P("h1", "8. Regulatory Information"))
    b.append(P("h2", "8.1 Classification"))
    b.append(P("body", "The CT-200 is classified as a Class II medical device under applicable regulations for "
                        "non-invasive blood pressure monitors and has been validated against relevant clinical "
                        "accuracy standards for oscillometric devices."))
    return b


def render(blocks, out_path):
    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                             topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                             leftMargin=0.9 * inch, rightMargin=0.9 * inch)
    flow = []
    for kind_tag, kind, payload in blocks:
        if kind_tag == "para":
            flow.append(Paragraph(payload, STYLES[kind]))
        elif kind_tag == "table":
            tbl = Table(payload, hAlign="LEFT", colWidths=None)
            tbl.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "DejaVuSans-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "DejaVuSans"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(Spacer(1, 4))
            flow.append(tbl)
            flow.append(Spacer(1, 8))
    doc.build(flow)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="data")
    args = ap.parse_args()
    render(build_blocks(1), f"{args.outdir}/ct200_manual_v1.pdf")
    render(build_blocks(2), f"{args.outdir}/ct200_manual_v2.pdf")
    print("done")
