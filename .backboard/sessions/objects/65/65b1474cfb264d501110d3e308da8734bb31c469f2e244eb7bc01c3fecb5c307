## Question

`rapidocr-onnxruntime` returns per-line/per-box text with individual confidence scores, not a single document-level confidence like Docling's `result.confidence`. What does its actual return shape look like, and how should we roll per-box scores into one `confidence` float that's meaningfully comparable to the existing `docling_confidence_threshold` — mean, min, or a weighted score over just the boxes that matched a required field?

This ticket resolves the extraction-shape contract for the new RapidOCR extractor. The answer determines whether `ExtractionResult.confidence` has a uniform meaning across Docling and RapidOCR, and whether `_needs_rapidocr_fallback` threshold logic works with a single scalar.

## Answer

RapidOCR's `engine(img)` returns a tuple `(det_lines, det_confidences)` or `(None, None)` when no text is detected.

- `det_lines` is `List[List[Union[ndarray, str, float]]]` where each element is `[box_coords, text, recognition_confidence]`.
- `det_confidences` is a separate list of detection-stage confidence scores (not recognition confidence).
- When no text is detected, both elements are `None`.

**Decision**: Use the mean of per-line recognition confidences (`line[2]` for each detected line) as the document-level `confidence` float. This is comparable to Docling's single scalar and works with the existing `docling_confidence_threshold` logic. When no text is detected, confidence is `0.0`.

**Resolution**: 2026-08-08. Frontier ticket resolved. The extraction shape is: text → regex → HRRecord, same as Docling's path. RapidOCR is an OCR engine, not a JSON-coercion engine, so `ExtractionResult.confidence` has a uniform meaning across both extractors.
