from __future__ import annotations

import os
from typing import List

try:
    import fitz
    import pytesseract
    from PIL import Image
    from io import BytesIO
except Exception:
    fitz = None
    pytesseract = None
    Image = None
    BytesIO = None

try:
    import pyautogui
except Exception:
    pyautogui = None


def ocr_pdf(path: str, pages: int = 2) -> str:
    if fitz is None or pytesseract is None or Image is None:
        raise RuntimeError("OCR dependencies missing: fitz/pytesseract/Pillow")
    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    parts: List[str] = []
    with fitz.open(path) as doc:
        max_pages = min(pages, doc.page_count)
        for i in range(max_pages):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=200)
            img = Image.open(BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img)
            parts.append(f"\n--- page {i+1} ---\n{text}")
    return "\n".join(parts)


def capture_screenshot(path: str) -> str:
    if pyautogui is None:
        raise RuntimeError("pyautogui not installed")
    image = pyautogui.screenshot()
    image.save(path)
    return path
