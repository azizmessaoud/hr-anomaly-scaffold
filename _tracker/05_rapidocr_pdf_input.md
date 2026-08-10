## Question

`vlm_path.py` needed explicit PDF→PNG conversion via `pypdfium2` before calling the model, because the VLM needed an image. Does `rapidocr-onnxruntime` accept PDFs directly, or does it also need page rasterization first — and if so, can it reuse the same `_pdf_to_image` approach, or does RapidOCR expect a different input shape (e.g. numpy array vs. file path)?

This is a task-style ticket. If RapidOCR accepts PDFs directly, the `_pdf_to_image` utility from `vlm_path.py` can be reused or removed entirely. If it needs rasterization first, we need to decide whether to share the `pypdfium2` approach or use a different library.

Label: wayfinder:task
Blocking: 01 (need to know the OCR return shape to decide the module boundary for PDF handling)

## Answer

RapidOCR's `engine.__call__` accepts `str | numpy.ndarray | bytes | pathlib.Path` — it does NOT accept PDFs directly. PDF pages must be rasterized to image arrays first.

The existing `_pdf_to_image` utility from `vlm_path.py` (using `pypdfium2`) renders the first page to a temp PNG. This can be reused for RapidOCR with a small adaptation: instead of saving to PNG and passing the file path, the rendered PIL image can be converted directly to a numpy array (HWC, RGB) and passed to RapidOCR. The `pypdfium2` dependency is already in the tree via docling.

**Resolution**: 2026-08-08. RapidOCR needs PDF→numpy array rasterization. The `_pdf_to_image` approach from `vlm_path.py` can be reused and adapted to return a numpy array directly instead of a temp PNG path.
