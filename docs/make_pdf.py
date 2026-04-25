"""Convert docs/project_overview.md into a PDF using markdown-pdf.

Run:
    python docs/make_pdf.py
"""

from pathlib import Path

from markdown_pdf import MarkdownPdf, Section

HERE = Path(__file__).resolve().parent
MD = HERE / "project_overview.md"
OUT = HERE / "project_overview.pdf"


CSS = """
body        { font-family: "Segoe UI", Arial, sans-serif; color: #1f2a3a; line-height: 1.55; }
h1          { color: #1e3a5f; border-bottom: 2px solid #2b6cb0; padding-bottom: 6px; margin-top: 18px; }
h2          { color: #1e3a5f; margin-top: 22px; border-bottom: 1px solid #cbd5e0; padding-bottom: 4px; }
h3          { color: #2b6cb0; margin-top: 18px; }
p, li       { font-size: 11.5pt; }
code        { background: #f1f5f9; padding: 2px 4px; border-radius: 3px; font-size: 10pt; }
pre         { background: #f1f5f9; padding: 10px; border-radius: 4px; font-size: 9.5pt; overflow-x: auto; }
pre code    { background: transparent; padding: 0; }
table       { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 10.5pt; }
th, td      { border: 1px solid #cbd5e0; padding: 6px 10px; text-align: left; vertical-align: top; }
th          { background: #e2e8f0; }
blockquote  { border-left: 4px solid #2b6cb0; padding-left: 10px; color: #4a5568; margin-left: 0; font-style: italic; }
img         { max-width: 100%; display: block; margin: 10px auto; }
em          { color: #4a5568; }
"""


def main():
    md_text = MD.read_text(encoding="utf-8")

    # markdown-pdf resolves image paths relative to the current working
    # directory, so run from the project root or docs/.
    pdf = MarkdownPdf(toc_level=2, optimize=True)
    pdf.add_section(Section(md_text, root=str(HERE)), user_css=CSS)

    pdf.meta["title"] = "NDWI Water-Body Segmentation — Project Overview"
    pdf.meta["author"] = "Tanmay Mandaliya · Rohan · Pravesh Khaparde"
    pdf.meta["subject"] = "GNR Semester 8 — NDWI + Mean-Shift water-body extraction"

    pdf.save(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
