"""Text extraction from PDF (PyMuPDF), images (OCR) and plain text / docx."""
from __future__ import annotations

import io
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


import os
import shutil

class ExtractionError(Exception):
    pass


def _get_pytesseract():
    try:
        import pytesseract  # type: ignore

        if not shutil.which("tesseract"):
            win_candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            ]
            for p in win_candidates:
                if os.path.isfile(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break
        return pytesseract
    except Exception:
        return None


def ocr_available() -> dict:
    from .. import config

    status = {"tesseract": False, "easyocr": False, "gemini": bool(config.GEMINI_API_KEY)}
    pt = _get_pytesseract()
    if pt:
        try:
            pt.get_tesseract_version()
            status["tesseract"] = True
        except Exception:
            pass
    try:
        import easyocr  # type: ignore  # noqa: F401

        status["easyocr"] = True
    except Exception:
        pass
    return status


def _format_easyocr_boxes(boxes: list) -> str:
    """Group bounding boxes by lines and columns to preserve document and table layout."""
    if not boxes:
        return ""
    items = []
    for item in boxes:
        if len(item) < 2:
            continue
        box = item[0]
        text = str(item[1]).strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        h = max(1.0, y1 - y0)
        ymid = (y0 + y1) / 2
        items.append({"x0": x0, "x1": x1, "y0": y0, "y1": y1, "ymid": ymid, "h": h, "text": text})

    if not items:
        return ""

    # Sort primarily by vertical position
    items.sort(key=lambda it: (it["y0"], it["x0"]))
    med_h = sorted(it["h"] for it in items)[len(items) // 2]
    line_threshold = max(10.0, med_h * 0.55)

    # Cluster into lines
    lines = []
    current_line = [items[0]]
    for it in items[1:]:
        line_ymid = sum(x["ymid"] for x in current_line) / len(current_line)
        if abs(it["ymid"] - line_ymid) <= line_threshold:
            current_line.append(it)
        else:
            current_line.sort(key=lambda x: x["x0"])
            lines.append(current_line)
            current_line = [it]
    if current_line:
        current_line.sort(key=lambda x: x["x0"])
        lines.append(current_line)

    # Build formatted text with proper column spacing
    formatted_lines = []
    for ln in lines:
        line_str = ""
        for i, it in enumerate(ln):
            if i == 0:
                line_str = it["text"]
            else:
                prev = ln[i - 1]
                gap = it["x0"] - prev["x1"]
                if gap > max(20.0, med_h * 1.1):
                    line_str += "  |  " + it["text"]
                elif gap > 3.0:
                    line_str += " " + it["text"]
                else:
                    line_str += " " + it["text"]
        formatted_lines.append(line_str)

    return "\n".join(formatted_lines)


def _ocr_image_bytes(data: bytes) -> str:
    """OCR with Tesseract, falling back to EasyOCR, and then Gemini Vision if API key is present."""
    # 1. Try Tesseract
    pt = _get_pytesseract()
    if pt:
        try:
            from PIL import Image  # type: ignore

            img = Image.open(io.BytesIO(data)).convert("RGB")
            res = pt.image_to_string(img).strip()
            if res:
                return res
        except Exception:
            pass

    # 2. Try EasyOCR with layout preservation
    try:
        from PIL import Image  # type: ignore
        import easyocr  # type: ignore
        import numpy as np

        global _EASY
        if _EASY is None:
            _EASY = easyocr.Reader(["en"], gpu=False)
        img = Image.open(io.BytesIO(data)).convert("RGB")
        raw_boxes = _EASY.readtext(np.array(img), detail=1, paragraph=False)
        res = _format_easyocr_boxes(raw_boxes).strip()
        if res:
            return res
    except Exception:
        pass

    # 3. Try Gemini Vision if API key is set
    from .. import config

    if config.GEMINI_API_KEY:
        try:
            import base64
            import requests

            b64 = base64.b64encode(data).decode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"inline_data": {"mime_type": "image/png", "data": b64}},
                            {
                                "text": (
                                    "Extract and transcribe all text from this circular notice image into a clean, "
                                    "well-structured format with clear headings, tables/columns, and bullet points."
                                )
                            },
                        ]
                    }
                ]
            }
            r = requests.post(url, params={"key": config.GEMINI_API_KEY}, json=payload, timeout=30)
            if r.ok:
                parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                res = "".join(p.get("text", "") for p in parts).strip()
                if res:
                    return res
        except Exception:
            pass

    raise ExtractionError(
        "OCR engine not available. Please run `pip install easyocr` in your backend terminal to read scanned circulars or images."
    )


def extract(path: Path) -> tuple[str, str]:
    """Return (text, kind) where kind is pdf | pdf+ocr | image-ocr | text | docx."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            try:
                import pymupdf as fitz  # PyMuPDF >= 1.24.3
            except ImportError:
                import fitz  # older PyMuPDF
        except ImportError as e:
            raise ExtractionError("PyMuPDF is not installed (pip install pymupdf)") from e
        doc = fitz.open(path)
        parts, used_ocr = [], False
        for page in doc:
            txt = page.get_text("text").strip()
            if len(txt) < 30:  # probably a scanned page -> OCR it
                pix = page.get_pixmap(dpi=200)
                try:
                    txt = _ocr_image_bytes(pix.tobytes("png"))
                    used_ocr = True
                except ExtractionError:
                    if not txt:
                        raise
            parts.append(txt)
        doc.close()
        return "\n\n".join(parts), ("pdf+ocr" if used_ocr else "pdf")
    if ext in IMAGE_EXT:
        return _ocr_image_bytes(path.read_bytes()), "image-ocr"
    if ext == ".docx":
        try:
            import docx  # type: ignore

            d = docx.Document(str(path))
            return "\n".join(p.text for p in d.paragraphs), "docx"
        except ImportError as e:
            raise ExtractionError("python-docx is not installed (pip install python-docx)") from e
    if ext in {".txt", ".md", ""}:
        return path.read_text(encoding="utf-8", errors="ignore"), "text"
    raise ExtractionError(f"Unsupported file type '{ext}'. Upload PDF, image, DOCX or TXT.")
