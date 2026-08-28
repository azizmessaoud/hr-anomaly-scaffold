#!/usr/bin/env python3
"""Run the synchronous pipeline for every supported document in a folder."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ingestion.doc_id import generate_doc_id  # noqa: E402
from app.ingestion.file_validation import SUPPORTED_EXTENSIONS  # noqa: E402
from app.ingestion.tasks import run_ingestion_pipeline  # noqa: E402
from app.pipeline.report import get_report_repository  # noqa: E402


def ingest_directory(input_dir: Path, output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for path in sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS):
        doc_id = generate_doc_id()
        job = run_ingestion_pipeline(path, doc_id)
        report = get_report_repository().get(doc_id)
        payload = {
            "file": str(path),
            "job": job.model_dump(mode="json"),
            "report": report.model_dump(mode="json") if report else None,
        }
        (output_dir / f"{doc_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        results.append(payload)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/reports"))
    args = parser.parse_args()
    if not args.input_dir.is_dir():
        parser.error(f"input directory not found: {args.input_dir}")
    for result in ingest_directory(args.input_dir, args.output_dir):
        job = result["job"]
        print(f"{result['file']}: {job['doc_id']} {job['statut']}")


if __name__ == "__main__":
    main()
