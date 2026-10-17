"""Generate editable vector diagrams and source data figures."""

from html import escape
from xml.etree import ElementTree as ET

import matplotlib

import matplotlib.pyplot as plt

from app.config import ROOT
from scripts.data import load_frames

matplotlib.use("Agg")

SCHEMA_NODES = [
    ("User", 70, 120, "user_id · anonymous identity"),
    ("Movie", 450, 120, "movie_id · title · year"),
    ("Genre", 830, 120, "name · controlled vocabulary"),
    ("TagApplication", 70, 390, "application_id · raw_text · time"),
    ("Tag", 450, 390, "key · normalized concept"),
    ("AnalyticsRun", 830, 390, "run_id · cutoff · version · status"),
    ("SystemState", 830, 650, "data_version · active_run_id"),
    ("Movie (another film)", 70, 650, "movie_id · title · year"),
]
SCHEMA_EDGES = [
    (0, 1, "RATED · score / time"),
    (1, 2, "IN_GENRE"),
    (0, 3, "APPLIED"),
    (3, 1, "ON_MOVIE"),
    (3, 4, "WITH_TAG"),
    (1, 5, "ANALYZED_IN · derived"),
    (6, 5, "active_run_id · reference"),
    (1, 7, "SIMILAR_TO · score / support"),
]
ARCH_NODES = [
    ("Browser / notebook", 70, 120, "HTTP clients · local demo"),
    ("Nginx", 450, 120, "localhost:18080 → internal :8000"),
    ("FastAPI", 830, 120, "Contracts · policy · safe compiler"),
    ("Batch jobs", 70, 390, "ETL · GDS · ML · evaluation"),
    ("Local Qwen model", 450, 390, "LM Studio · host :1234/v1"),
    ("Neo4j + GDS", 830, 390, "Bolt :17687 · Browser :17474"),
]
ARCH_EDGES = [
    (0, 1, "HTTP"),
    (1, 2, "HTTP"),
    (2, 5, "Bolt · parameter binding"),
    (2, 4, "validated JSON plan"),
    (3, 5, "trusted management driver"),
]


def diagram(name: str, title: str, subtitle: str, nodes: list, edges: list):
    """Render the same graph to standalone SVG and native editable draw.io XML."""
    width, height = 1160, 850
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#708e7d"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#f7f6f2"/>',
        f'<text x="70" y="52" font-family="Georgia" font-size="30" fill="#17313c">{escape(title)}</text>',
        f'<text x="70" y="83" font-family="Arial" font-size="13" fill="#7e8f83">{escape(subtitle)}</text>',
    ]
    mxfile = ET.Element("mxfile", host="app.diagrams.net")
    mxdiagram = ET.SubElement(mxfile, "diagram", name=title)
    model = ET.SubElement(mxdiagram, "mxGraphModel", grid="1", page="1", pageWidth=str(width), pageHeight=str(height))
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    for index, (label, xpos, ypos, fields) in enumerate(nodes):
        svg.extend(
            [
                f'<rect x="{xpos}" y="{ypos}" width="250" height="90" rx="9" fill="#e8ede3" stroke="#bdccbb"/>',
                f'<text x="{xpos+18}" y="{ypos+36}" font-family="Georgia" font-size="23" fill="#17313c">{escape(label)}</text>',
                f'<text x="{xpos+18}" y="{ypos+63}" font-family="Arial" font-size="11" fill="#70846e">{escape(fields)}</text>',
            ]
        )
        cell = ET.SubElement(
            root,
            "mxCell",
            id=f"n{index}",
            value=label + "\n" + fields,
            vertex="1",
            parent="1",
            style="rounded=1;whiteSpace=wrap;fillColor=#e8ede3;strokeColor=#bdccbb;fontColor=#17313c;",
        )
        ET.SubElement(cell, "mxGeometry", x=str(xpos), y=str(ypos), width="250", height="90", **{"as": "geometry"})
    for index, (source, target, label) in enumerate(edges):
        _, left, top, _ = nodes[source]
        _, right, bottom, _ = nodes[target]
        if name == "architecture" and source == 3:
            path = f"M{left+125} {top+90} V560 H{right+125} V{bottom+90}"
            tx = 530
            ty = 580
        elif top == bottom:
            path = f"M{left+250} {top+45} L{right} {bottom+45}"
            tx = (left + 250 + right) / 2
            ty = top + 30
        elif name == "schema" and source == 1 and target == 7:
            path = "M575 210 V260 H385 V695 H320"
            tx = 385
            ty = 565
        elif left == right:
            path = f"M{left+125} {top+90 if bottom>top else top} L{right+125} {bottom if bottom>top else bottom+90}"
            tx = left + 135
            ty = (top + 90 + bottom) / 2
        else:
            path = f"M{left+125} {top+90 if bottom>top else top} L{right+125} {bottom if bottom>top else bottom+90}"
            tx = (left + right) / 2 + 125
            ty = (top + bottom) / 2 + 45
        dashed = (
            'stroke-dasharray="5 4"' if any(word in label for word in ["derived", "reference", "SIMILAR_TO"]) else ""
        )
        svg.append(
            f'<path d="{path}" fill="none" stroke="#708e7d" stroke-width="1.5" {dashed} marker-end="url(#arrow)"/>'
        )
        svg.append(
            f'<text x="{tx}" y="{ty}" text-anchor="middle" font-family="Arial" font-size="11" fill="#b06f4d">{escape(label)}</text>'
        )
        cell = ET.SubElement(
            root,
            "mxCell",
            id=f"e{index}",
            value=label,
            edge="1",
            parent="1",
            source=f"n{source}",
            target=f"n{target}",
            style="edgeStyle=orthogonalEdgeStyle;rounded=0;endArrow=block;strokeColor=#708e7d;",
        )
        ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
    note = (
        "SIMILAR_TO: Movie → Movie · score / support / run_id · no self-links. Dashed semantics: derived analytics."
        if name == "schema"
        else "Three persistent services. Batch CLI reuses application code. Model stays on the local host."
    )
    svg.append(f'<text x="70" y="800" font-family="Arial" font-size="12" fill="#7e8f83">{escape(note)}</text></svg>')
    folder = ROOT / "docs/diagrams"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.svg").write_text("\n".join(svg))
    ET.ElementTree(mxfile).write(folder / f"{name}.drawio", encoding="utf-8", xml_declaration=True)


def figures():
    """Plot actual rating distributions and measured algorithm/ML results."""
    frames = load_frames()
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.facecolor": "#f7f6f2",
            "figure.facecolor": "#f7f6f2",
            "text.color": "#17313c",
            "axes.labelcolor": "#17313c",
            "axes.edgecolor": "#bcc7ba",
        }
    )
    figure, axes = plt.subplots(1, 2, figsize=(11, 3.8), layout="constrained")
    frames["ratings"].rating.value_counts().sort_index().plot.bar(ax=axes[0], color="#758f7c", width=0.75)
    axes[0].set(title="Every rating is an observed connection", xlabel="Rating", ylabel="Count")
    frames["ratings"].groupby("movieId").size().plot.hist(ax=axes[1], bins=45, color="#cf8867", log=True)
    axes[1].set(title="A catalog with a long tail", xlabel="Ratings per movie", ylabel="Movies (log scale)")
    figure.savefig(ROOT / "docs/evidence/data-profile.png", dpi=180)
    plt.close(figure)


def main():
    """Regenerate source-controlled visual documentation from source definitions."""
    diagram(
        "schema",
        "The graph behind the recommendation",
        "Observed source events and versioned analytical output",
        SCHEMA_NODES,
        SCHEMA_EDGES,
    )
    diagram(
        "architecture",
        "One product. Clear boundaries.",
        "Services, ports and trusted data flows",
        ARCH_NODES,
        ARCH_EDGES,
    )
    figures()
    print("Editable diagrams and real data figure generated")


if __name__ == "__main__":
    main()
