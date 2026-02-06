from __future__ import annotations

import base64
import os
from typing import List

try:
    import fitz
    import pytesseract
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO
except Exception:
    fitz = None
    pytesseract = None
    Image = None
    ImageDraw = None
    ImageFont = None
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


def encode_image_data_url(path: str) -> str:
    with open(path, "rb") as handle:
        data = handle.read()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def capture_screenshot_with_grid(path: str, grid_size: int = 6) -> str:
    if pyautogui is None:
        raise RuntimeError("pyautogui not installed")
    image = pyautogui.screenshot()
    if ImageDraw is None:
        image.save(path)
        return path
    draw = ImageDraw.Draw(image)
    width, height = image.size
    cell_w = width / grid_size
    cell_h = height / grid_size
    line_color = (255, 215, 0)
    text_color = (255, 0, 0)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    for i in range(1, grid_size):
        x = int(i * cell_w)
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)
    for j in range(1, grid_size):
        y = int(j * cell_h)
        draw.line([(0, y), (width, y)], fill=line_color, width=1)
    idx = 1
    for r in range(grid_size):
        for c in range(grid_size):
            tx = int(c * cell_w + 4)
            ty = int(r * cell_h + 4)
            draw.text((tx, ty), str(idx), fill=text_color, font=font)
            idx += 1
    image.save(path)
    return path
