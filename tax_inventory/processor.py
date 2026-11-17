from __future__ import annotations

import io
import re
from typing import Any

import pymupdf
import pytesseract
from PIL import Image, ImageOps

from .tesseract_runtime import configure_tesseract

configure_tesseract()

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    # HEIC support is optional at runtime; the UI will report a useful error.
    pass

from .classifier import (
    amounts_key,
    classify_page,
    copy_label,
    extract_issuer,
    extract_tax_year,
    has_continuation_text,
    page_number_hint,
)
from .layout import Segment, extract_issuer_from_layout, segments_to_text, words_to_segments

MIN_NATIVE_TEXT_CHARS = 45


def _ocr_pil_image(image: Image.Image) -> tuple[str, list[list[Segment]]]:
    """OCR image locally using the installed Tesseract binary.

    Returns the page text and its visual rows. Boxed form layouts make each
    Tesseract page-segmentation mode drop different words, so an automatic
    layout pass (psm 3) is supplemented by a sparse-text pass (psm 11) for
    regions the first pass missed. Rows are then rebuilt from word positions.
    """
    image = ImageOps.exif_transpose(image).convert("RGB")
    # Tesseract's orientation detection is best-effort and can fail on small
    # images; a failure should not prevent the regular OCR pass.
    try:
        osd = pytesseract.image_to_osd(image)
        match = re.search(r"Rotate:\s*(\d+)", osd)
        if match and int(match.group(1)) in (90, 180, 270):
            image = image.rotate(-int(match.group(1)), expand=True)
    except Exception:
        pass
    words = _ocr_words(image, psm=3)
    for word in _ocr_words(image, psm=11):
        if not any(_overlap(word, existing) > 0.3 for existing in words):
            words.append(word)
    rows = words_to_segments(words)
    return segments_to_text(rows), rows


def _ocr_words(image: Image.Image, psm: int) -> list[tuple[float, float, float, float, str]]:
    data = pytesseract.image_to_data(image, config=f"--oem 3 --psm {psm}", output_type=pytesseract.Output.DICT)
    return [
        (left, top, left + width, top + height, text)
        for left, top, width, height, text, conf in zip(
            data["left"], data["top"], data["width"], data["height"], data["text"], data["conf"]
        )
        if text.strip() and float(conf) >= 0
    ]


def _overlap(a: tuple, b: tuple) -> float:
    """Fraction of box a's area covered by box b."""
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    if width <= 0 or height <= 0:
        return 0.0
    return width * height / max((a[2] - a[0]) * (a[3] - a[1]), 1)


def _page_record(
    page_number: int, text: str, source_kind: str, ocr_used: bool, rows: list[list[Segment]]
) -> dict[str, Any]:
    classification = classify_page(text)
    page_hint, page_total_hint = page_number_hint(text)
    stripped = text.strip()
    is_blank = len(stripped) < 8
    warnings = []
    if is_blank:
        warnings.append("Page appears blank or contains too little readable text.")
    elif ocr_used and len(stripped) < 45:
        warnings.append("OCR returned very little text; check image quality and page completeness.")
    if classification["type"] == "UNKNOWN" and not is_blank:
        warnings.append("No configured classification rule matched this page.")
    if classification.get("is_instructions"):
        warnings.append("Page looks like form instructions rather than form data.")
    return {
        "page_number": page_number,
        "source_kind": source_kind,
        "ocr_used": ocr_used,
        "text_chars": len(stripped),
        "text_excerpt": stripped[:900],
        "classification": classification,
        "tax_year": extract_tax_year(text),
        "issuer": extract_issuer_from_layout(rows) or extract_issuer(text),
        "printed_page_number": page_hint,
        "printed_page_total": page_total_hint,
        # Checked against the full page text; continuation labels are often in the footer.
        "has_continuation_text": has_continuation_text(text),
        "copy_label": copy_label(text),
        # Digest only, so identical copies can be matched without exporting amounts.
        "amounts_key": amounts_key(text),
        "is_blank": is_blank,
        "warnings": warnings,
    }


def process_pdf(data: bytes) -> list[dict[str, Any]]:
    records = []
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    if document.needs_pass:
        document.close()
        raise ValueError("This PDF is password-protected. Remove the password locally before testing.")

    try:
        for index, page in enumerate(document):
            text = page.get_text("text") or ""
            rows = words_to_segments(w[:5] for w in page.get_text("words"))
            ocr_used = False
            if len(text.strip()) < MIN_NATIVE_TEXT_CHARS:
                pix = page.get_pixmap(dpi=250, alpha=False)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    text, rows = _ocr_pil_image(image)
                    ocr_used = True
                except pytesseract.pytesseract.TesseractNotFoundError as exc:
                    raise RuntimeError(
                        "Tesseract was not found. Install the Tesseract OCR application and ensure it is on PATH."
                    ) from exc
            records.append(_page_record(index + 1, text, "pdf", ocr_used, rows))
    finally:
        document.close()
    return records


def process_image(data: bytes) -> list[dict[str, Any]]:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except Exception as exc:
        raise ValueError(
            "Could not open image. Supported inputs are JPEG, PNG, TIFF, and HEIC/HEIF (with pillow-heif installed)."
        ) from exc
    try:
        text, rows = _ocr_pil_image(image)
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract was not found. Install the Tesseract OCR application and ensure it is on PATH."
        ) from exc
    return [_page_record(1, text, "image", True, rows)]


def process_upload(filename: str, data: bytes) -> list[dict[str, Any]]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        return process_pdf(data)
    if suffix in {"jpg", "jpeg", "png", "tif", "tiff", "heic", "heif", "webp"}:
        return process_image(data)
    raise ValueError("Unsupported file type. Upload one PDF or one image (JPG, PNG, TIFF, HEIC/HEIF, or WEBP).")
