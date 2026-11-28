"""Create the concise Word description of the deployed Florida estimators.

Run with the Python runtime supplied by load_workspace_dependencies, then render
the output with the documents skill's render_docx.py for visual verification.
"""
from pathlib import Path
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/Florida_Trajectory_Reconstruction_Methodology.docx"
FIGURES = ROOT / "docs/figures/trajectory-methodology"

TEXT = (
    "We reconstruct missing Florida trajectories in two stages: matching recorded fragments and estimating the motion between them. "
    "Within an intersection, we join compatible fragments with the same sensor, recording session and object ID, even if their classification changes. "
    "Endpoint positions and speeds define a cubic Hermite curve, with monotonicity checks to avoid backward motion [1]. "
    "The primary estimator uses Sequential Least Squares Programming (SLSQP) to preserve endpoint positions, enforce speed and acceleration limits, "
    "and penalize abrupt acceleration changes [2]. A separate same-ID fallback can limit noisy endpoint slopes; unreliable timing is flagged. "
    "Between consecutive intersections, IDs are not assumed to match. Departures and arrivals are screened by direction and known corridor exits, "
    "then scored using travel time, speed, vehicle size and forward/backward motion agreement. Acceleration is extrapolated for at most three seconds. "
    "A minimum-cost one-to-one assignment, solved with the modified Jonker-Volgenant algorithm, permits unmatched fragments and rejects ambiguous pairings [3]. "
    "Accepted pairs receive constrained smooth curves. Optional layers add same-speed constant-slope extensions or weaker gray matches; "
    "the corrected gray matcher preserves endpoint slopes and rejects physically incompatible curves. Original observations remain solid and estimates are dashed. "
    "We assess reconstruction by hiding recorded segments and comparing estimates with the withheld observations. "
    "Cross-sensor identities remain unverified, and estimates are excluded from measured KPIs. "
    "This custom pipeline uses established numerical methods; the displayed estimates do not currently use DeepCTM or verified signal constraints."
)


def link(paragraph, label, url):
    element = OxmlElement("w:hyperlink")
    element.set(qn("r:id"), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "245D86")
    props.append(color)
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "18")
    props.append(size)
    run.append(props)
    text = OxmlElement("w:t")
    text.text = label
    run.append(text)
    element.append(run)
    paragraph._p.append(element)


def field(paragraph, instruction, value):
    """Editable Word field with a cached result for reliable rendering."""
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    code = OxmlElement("w:instrText"); code.set(qn("xml:space"), "preserve")
    code.text = f" {instruction} "
    separate = OxmlElement("w:fldChar"); separate.set(qn("w:fldCharType"), "separate")
    run._r.extend([begin, code, separate])
    paragraph.add_run(str(value))
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(end)


def figure_ref(paragraph, number):
    paragraph.add_run("Figure ")
    field(paragraph, f"REF fig{number} " + r"\h", number)


def caption(doc, number, text):
    p = doc.add_paragraph(style="Caption")
    p.add_run("Figure ")
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(number)); start.set(qn("w:name"), f"fig{number}")
    p._p.append(start)
    field(p, r"SEQ Figure \* ARABIC", number)
    end = OxmlElement("w:bookmarkEnd"); end.set(qn("w:id"), str(number))
    p._p.append(end)
    p.add_run(". " + text)
    p.paragraph_format.keep_together = True


def add_screenshot(doc, filename, alt):
    p = doc.add_paragraph()
    # Inline pictures need automatic line height, not the body's exact leading.
    p.paragraph_format.line_spacing = 1
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    picture = p.add_run().add_picture(str(FIGURES / filename), width=Inches(6.8))
    picture._inline.docPr.set("descr", alt)


def clock(epoch):
    return datetime.fromtimestamp(epoch, ZoneInfo("America/New_York")).strftime("%H:%M:%S.%f")[:-3]


def add_examples(doc, examples):
    start = examples["snapshot_start"]
    local, between = examples["local"], examples["between"]
    doc.add_page_break()
    doc.add_paragraph("Missing observations within an intersection", style="Heading 1")
    p = doc.add_paragraph()
    figure_ref(p, 1)
    p.add_run(" shows westbound vehicles at Essex Avenue on November 27, 2026. "
              "Solid lines stop where observations are missing; the dashed portions bridge compatible fragments. "
              "Only the within-intersection estimate layer is enabled in this example.")
    add_screenshot(doc, "within-after.jpg", "Essex westbound trajectories from 11:47:33 to 11:47:56, with dashed same-sensor estimates spanning missing observations.")
    caption(doc, 1, "Within-intersection reconstruction at Essex Avenue and SR-436, "
            "11:47:33–11:47:56 Florida time. Fifteen local estimates are visible. "
            "Red indicates slow motion; yellow and green indicate increasing speed, not signal color.")
    a, b = local["points"][0], local["points"][-1]
    dt, dx = b[0]-a[0], abs(b[1]-a[1])
    p = doc.add_paragraph()
    p.add_run("Worked example. ").bold = True
    p.add_run(f"Object {local['object_id']} is observed at station {a[1]:.2f} m at {clock(start+a[0])} "
              f"and at {b[1]:.2f} m at {clock(start+b[0])}, in the same sensor session. "
              f"The gap is {dt:.2f} s across {dx:.2f} m, requiring a mean speed of {dx/dt:.2f} m/s. "
              f"Endpoint slopes estimated from the visible motion are {a[2]:.2f} and {b[2]:.2f} m/s.")
    p = doc.add_paragraph()
    p.add_run("The estimator fixes both endpoint positions, follows those endpoint slopes, and uses the constrained "
              "smooth-curve fit described on page 1 [2]. The dashed curve therefore speeds up across the gap "
              "while the recorded pieces remain unchanged. The decreasing station value means westbound travel. "
              "The cause of the observation gap is not established by this image; it is not proof of a server outage.")

    doc.add_page_break()
    doc.add_paragraph("Missing observations between intersections", style="Heading 1")
    p = doc.add_paragraph()
    figure_ref(p, 2)
    p.add_run(" shows eastbound travel from Palm Springs Drive toward Boston Avenue. "
              "The matching stage chooses candidate departures and arrivals before estimating the unobserved motion. "
              "Only the between-intersection estimate layer is enabled; weaker gray matches are hidden.")
    add_screenshot(doc, "between-after.jpg", "Palm Springs and Boston eastbound trajectories from 11:47:10 to 11:47:38, with seven dashed cross-sensor connection hypotheses.")
    caption(doc, 2, "Between-intersection reconstruction from Palm Springs Drive to Boston Avenue, "
            "11:47:10–11:47:38 Florida time on November 27, 2026. Seven estimated connections are visible. "
            "Dashed speed colors describe inferred motion; vehicle identity across sensors is unverified.")
    a, b = between["points"][0], between["points"][-1]
    dt, dx = b[0]-a[0], abs(b[1]-a[1])
    departure = between["endpoint_provenance"]["departure"]["source_key"][1]
    arrival = between["endpoint_provenance"]["arrival"]["source_key"][1]
    p = doc.add_paragraph()
    p.add_run("Worked example. ").bold = True
    p.add_run(f"Palm Springs object {departure} ends at {a[1]:.2f} m at {clock(start+a[0])}. "
              f"Boston object {arrival} begins at {b[1]:.2f} m at {clock(start+b[0])}. "
              f"Connecting these different local IDs requires {dx:.2f} m in {dt:.2f} s, "
              f"or {dx/dt:.2f} m/s on average. The fitted endpoint speeds are {a[2]:.2f} and {b[2]:.2f} m/s, "
              "derived from neighboring observed positions.")
    p = doc.add_paragraph()
    p.add_run("The eastbound direction, travel time and motion agreement make this pair an eligible candidate. "
              "The one-to-one assignment compares it with competing arrivals [3], then the smooth fit joins its "
              "endpoints [2]. Other candidates can remain unmatched. This illustrates a plausible connection, "
              "not confirmed identity or a measured trajectory; it remains excluded from measured KPIs.")


def main():
    examples = json.loads((FIGURES / "examples.json").read_text())
    doc = Document()
    # The bundled base template can carry Word's blue Title border.
    # Remove paragraph borders from the inherited styles as well as the content.
    for style in doc.styles:
        for border in list(style.element.iter(qn("w:pBdr"))):
            border.getparent().remove(border)
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(1)
    section.left_margin = section.right_margin = Inches(0.85)
    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.line_spacing = Pt(12.5)
    normal.paragraph_format.space_after = Pt(5)
    title = doc.styles["Title"]
    title.font.name = "Arial"
    title.font.size = Pt(14)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.space_after = Pt(7)
    title.paragraph_format.line_spacing = 1
    heading = doc.styles["Heading 1"]
    heading.font.name = "Arial"; heading.font.size = Pt(14)
    heading.font.bold = True; heading.font.color.rgb = RGBColor(0, 0, 0)
    heading.paragraph_format.space_before = Pt(0)
    heading.paragraph_format.space_after = Pt(7)
    cap = doc.styles["Caption"]
    cap.font.name = "Arial"; cap.font.size = Pt(9)
    cap.font.italic = False; cap.font.bold = False; cap.font.color.rgb = RGBColor(0, 0, 0)
    cap.paragraph_format.line_spacing = Pt(11)
    cap.paragraph_format.space_after = Pt(7)
    doc.add_paragraph("Florida Trajectory Reconstruction", style="Title")
    doc.add_paragraph(TEXT)
    p = doc.add_paragraph()
    figure_ref(p, 1); p.add_run(" and "); figure_ref(p, 2)
    p.add_run(" illustrate both tasks using the November 27 live-data recording published at 11:48:21 Florida time. "
              "They demonstrate the displayed estimates, not hidden-data validation: the actual paths inside these gaps are unknown. "
              "Times use the receipt-based display timeline; sensor clock offsets and spatial alignment remain unverified.")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(3)
    p.add_run("References").bold = True
    references = [
        ("[1] Fritsch, F. N., & Carlson, R. E. (1980). Monotone piecewise cubic interpolation. SIAM Journal on Numerical Analysis, 17(2), 238-246. ",
         "doi:10.1137/0717021", "https://doi.org/10.1137/0717021"),
        ("[2] Kraft, D. (1988). A software package for sequential quadratic programming. DFVLR-FB 88-28. ",
         "SLSQP documentation", "https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html"),
        ("[3] Crouse, D. F. (2016). On implementing 2D rectangular assignment algorithms. IEEE Transactions on Aerospace and Electronic Systems, 52(4), 1679-1696. ",
         "doi:10.1109/TAES.2016.140952", "https://doi.org/10.1109/TAES.2016.140952"),
    ]
    for body, label, url in references:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = Pt(10.8)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.19)
        p.paragraph_format.first_line_indent = Inches(-0.19)
        p.paragraph_format.keep_together = True
        run = p.add_run(body)
        run.font.size = Pt(9)
        link(p, label, url)
    add_examples(doc, examples)
    doc.core_properties.title = "Florida Trajectory Reconstruction"
    doc.core_properties.subject = "Within-intersection and between-intersection estimation methods"
    doc.core_properties.author = "Ouster Corridor Project"
    doc.core_properties.keywords = "trajectory reconstruction, interpolation, assignment, Florida"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"Saved {OUTPUT}; methodology words: {len(TEXT.split())}")


if __name__ == "__main__":
    main()
