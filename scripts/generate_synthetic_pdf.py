#!/usr/bin/env python3
"""Generate synthetic HR PDFs for testing the anomaly pipeline.

Creates PDFs with known fields that match the regex parser patterns.
Use these as golden-test fixtures.

Usage:
    python scripts/generate_synthetic_pdf.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "synthetic"

# --- Known-good field values (Tunisian HR conventions) ---

SAMPLE_RECORDS = [
    {
        "nom": "BEN ALI",
        "prenom": "Ahmed",
        "cin": "AB12345",
        "cnss": "198765432",
        "date_embauche": "15/03/2020",
        "salaire_brut": "1850,00",
        "poste": "Ingénieur",
        "direction": "Direction des Systèmes d'Information",
    },
    {
        "nom": "TRABELSI",
        "prenom": "Fatma",
        "cin": "CD98765",
        "cnss": "123456789",
        "date_embauche": "2021-06-01",
        "salaire_brut": "2 200,50",
        "poste": "Analyste RH",
        "direction": "Direction des Ressources Humaines",
    },
    {
        "nom": "MAALEJ",
        "prenom": "Sami",
        "cin": "EF87654",
        "cnss": "111222333",
        "date_embauche": "01/01/2019",
        "salaire_brut": "3200",
        "poste": "Chef de projet",
        "direction": "Direction Finance",
    },
    {
        "nom": "BEN SALAH",
        "prenom": "Leila",
        "cin": "GH56789",
        "cnss": "999888777",
        "date_embauche": "2022/11/15",
        "salaire_brut": "1 450.75",
        "poste": "Technicienne",
        "direction": "Direction Technique",
    },
]


def _build_text(record: dict) -> str:
    """Build human-readable text for a PDF page."""
    lines = [
        f"{record['nom']} {record['prenom']}",
        f"Matricule CIN: {record['cin']}",
        f"N° CNSS: {record['cnss']}",
        f"Date d'embauche: {record['date_embauche']}",
        f"Salaire brut mensuel: {record['salaire_brut']} DT",
        f"Poste: {record['poste']}",
        f"Direction: {record['direction']}",
    ]
    return "\n".join(lines)


def generate_pdf_pypdfium2(record: dict, output_path: Path) -> None:
    """Generate a simple single-page PDF using pypdfium2."""
    import pypdfium2 as pdfium

    text = _build_text(record)

    # Create a basic PDF document with text
    pdf = pdfium.PdfDocument.new()

    # Add a single page (A4 = 595 x 842 points)
    page_width, page_height = 595, 842
    page = pdf.new_page(page_width, page_height)

    # Use a simple canvas approach: write text via pdfium's text API
    # pdfium can add text via the page's text insertion
    # We'll use a minimal approach: create a page and insert text positions
    # For simplicity, use a helper that creates text in the PDF

    # Actually, pypdfium2 text insertion is limited. Let's use a file-based approach
    # with reportlab or fpdf if available, otherwise use pypdfium2's raw API.

    # Fallback: use fpdf2 if available
    try:
        from fpdf import FPDF

        pdf_doc = FPDF()
        pdf_doc.add_page()
        pdf_doc.set_font("Helvetica", size=11)

        for line in text.split("\n"):
            pdf_doc.cell(0, 8, txt=line, new_x="LMARGIN", new_y="NEXT")

        pdf_doc.output(str(output_path))
        return
    except ImportError:
        pass

    # Fallback: use reportlab if available
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(output_path), pagesize=A4)
        y = A4[1] - 50  # start from top
        c.setFont("Helvetica", 11)
        for line in text.split("\n"):
            c.drawString(50, y, line)
            y -= 18
        c.save()
        return
    except ImportError:
        pass

    # Last resort: use pypdfium2 raw text rendering
    # Create a minimal valid PDF manually with embedded text
    _write_manual_pdf(text, output_path)


def _write_manual_pdf(text: str, output_path: Path) -> None:
    """Write a minimal PDF with text using raw PDF syntax."""
    lines = text.split("\n")
    content_lines = []
    y = 750  # start near top of page
    for line in lines:
        # Escape special PDF chars
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"1 0 0 1 50 {y} Tm ({safe}) Tj")
        y -= 18

    content_stream = "\n".join(content_lines)

    pdf_bytes = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj

4 0 obj
<< /Length {len(content_stream)} >>
stream
BT
/F1 11 Tf
{content_stream}
ET
endstream
endobj

5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000{len(content_stream) + 340:09d} 00000 n 

trailer
<< /Size 6 /Root 1 0 R >>
startxref
{len(content_stream) + 440}
%%EOF
""".encode()

    output_path.write_bytes(pdf_bytes)


def generate_all(output_dir: Path | None = None) -> list[Path]:
    """Generate all synthetic PDFs."""
    out = output_dir or DATA_DIR
    out.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, record in enumerate(SAMPLE_RECORDS):
        filename = f"hr_record_{i+1:02d}.pdf"
        path = out / filename
        generate_pdf_pypdfium2(record, path)
        paths.append(path)
        print(f"  Created: {path}")

    # Write manifest
    manifest = []
    for i, record in enumerate(SAMPLE_RECORDS):
        manifest.append({
            "file": f"hr_record_{i+1:02d}.pdf",
            "fields": record,
        })

    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"  Manifest: {manifest_path}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic HR PDFs")
    parser.add_argument("--output", type=Path, default=DATA_DIR, help="Output directory")
    args = parser.parse_args()

    print("Generating synthetic HR PDFs...")
    paths = generate_all(args.output)
    print(f"Done. Generated {len(paths)} PDFs in {args.output}")


if __name__ == "__main__":
    main()
