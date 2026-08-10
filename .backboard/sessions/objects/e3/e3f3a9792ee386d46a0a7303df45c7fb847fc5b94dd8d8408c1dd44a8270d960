#!/usr/bin/env python3
"""Standalone diagnostic tool for HR PDF files.

Runs Docling + RapidOCR on a PDF and prints raw text, parsed fields,
and flags. Use this to understand why a specific file gets AMBER status.

Usage:
    python scripts/diagnose_pdf.py path/to/file.pdf [--engine both|docling|rapidocr]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("diagnose")

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _split_text_fields(raw_text: str) -> dict[str, str]:
    """Show regex parsing results on raw text."""
    from app.ingestion.parser_regex import (
        parse_cin,
        parse_cnss,
        parse_date_embauche,
        parse_name,
        parse_salaire,
    )

    return {
        "name": parse_name(raw_text),
        "cin": parse_cin(raw_text),
        "cnss": parse_cnss(raw_text),
        "date_embauche": parse_date_embauche(raw_text),
        "salaire": parse_salaire(raw_text),
    }


def diagnose(file_path: Path, engine: str = "both") -> dict:
    """Run diagnostics on a PDF file."""
    results: dict = {"file": str(file_path), "engine": engine}

    if engine in ("docling", "both"):
        log.info("Running Docling on %s", file_path)
        from app.ingestion.docling_path import extract_from_docling
        from app.core.config import Settings, make_extract_pipeline_config

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        docling_res = extract_from_docling(file_path, config=cfg)
        results["docling"] = {
            "succeeded": docling_res.succeeded,
            "erreur_traitement": docling_res.erreur_traitement,
            "confidence": docling_res.confidence,
            "flags": list(docling_res.flags),
        }
        if docling_res.record:
            r = docling_res.record
            results["docling"]["record"] = {
                "nom": r.nom,
                "prenom": r.prenom,
                "cin": r.cin,
                "cnss": r.cnss,
                "date_embauche": str(r.date_embauche) if r.date_embauche else None,
                "salaire_brut": float(r.salaire_brut) if r.salaire_brut else None,
                "poste": r.poste,
                "departement": r.departement,
            }
        # Also show raw text if available via a second extraction
        log.info("  Docling succeeded=%s confidence=%.3f", docling_res.succeeded, docling_res.confidence)

    if engine in ("rapidocr", "both"):
        log.info("Running RapidOCR on %s", file_path)
        from app.ingestion.rapidocr_path import extract_with_rapidocr
        from app.core.config import Settings, make_extract_pipeline_config

        settings = Settings()
        cfg = make_extract_pipeline_config(settings)
        rapidocr_res = extract_with_rapidocr(file_path, config=cfg, doc_id="diag")
        results["rapidocr"] = {
            "succeeded": rapidocr_res.succeeded,
            "erreur_traitement": rapidocr_res.erreur_traitement,
            "confidence": rapidocr_res.confidence,
            "flags": list(rapidocr_res.flags),
        }
        if rapidocr_res.record:
            r = rapidocr_res.record
            results["rapidocr"]["record"] = {
                "nom": r.nom,
                "prenom": r.prenom,
                "cin": r.cin,
                "cnss": r.cnss,
                "date_embauche": str(r.date_embauche) if r.date_embauche else None,
                "salaire_brut": float(r.salaire_brut) if r.salaire_brut else None,
                "poste": r.poste,
                "departement": r.departement,
            }
        log.info("  RapidOCR succeeded=%s confidence=%.3f", rapidocr_res.succeeded, rapidocr_res.confidence)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose a PDF for HR anomaly pipeline")
    parser.add_argument("file", type=Path, help="Path to PDF file")
    parser.add_argument(
        "--engine",
        choices=["both", "docling", "rapidocr"],
        default="both",
        help="Which engine to run (default: both)",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    results = diagnose(args.file, engine=args.engine)
    print(json.dumps(results, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
