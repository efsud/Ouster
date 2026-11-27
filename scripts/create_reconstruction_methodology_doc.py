"""Create the concise Word description of the deployed Florida estimators.

Run with the Python runtime supplied by load_workspace_dependencies, then render
the output with the documents skill's render_docx.py for visual verification.
"""
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/Florida_Trajectory_Reconstruction_Methodology.docx"

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


def main():
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
    doc.add_paragraph("Florida Trajectory Reconstruction", style="Title")
    doc.add_paragraph(TEXT)
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
    doc.core_properties.title = "Florida Trajectory Reconstruction"
    doc.core_properties.subject = "Within-intersection and between-intersection estimation methods"
    doc.core_properties.author = "Ouster Corridor Project"
    doc.core_properties.keywords = "trajectory reconstruction, interpolation, assignment, Florida"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"Saved {OUTPUT}; methodology words: {len(TEXT.split())}")


if __name__ == "__main__":
    main()
