"""PDF OCR tool using RapidOCR (ONNX) for image-based / scanned PDFs.

No external OCR engine (Tesseract) required.
PyMuPDF renders pages to images, RapidOCR extracts text via ONNX inference.
"""
import fitz
import cv2
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR


class PDFOCR:
    """OCR for scanned/image-based PDFs."""

    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self._engine = None

    @property
    def engine(self) -> RapidOCR:
        if self._engine is None:
            self._engine = RapidOCR()
        return self._engine

    def extract(self, file_path: str, pages: list[int] | None = None) -> dict:
        """Extract text from PDF via OCR.

        Returns dict with per-page text blocks and concatenated full_text.
        """
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        doc = fitz.open("pdf", pdf_bytes)

        results = []
        page_range = pages or range(len(doc))

        for page_num in page_range:
            page = doc[page_num]
            pix = page.get_pixmap(dpi=self.dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Preprocess: grayscale + binary threshold for better OCR accuracy
            img_gray = img.convert("L")
            img_np = np.array(img_gray)
            _, img_bin = cv2.threshold(img_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            ocr_result, _ = self.engine(img_bin)

            blocks = []
            if ocr_result:
                for box, text, confidence in ocr_result:
                    blocks.append({
                        "text": text,
                        "confidence": round(float(confidence), 4),
                        "box": [[int(c) for c in pt] for pt in box],
                    })

            full_text = "\n".join(b["text"] for b in blocks) if blocks else ""

            results.append({
                "page": page_num,
                "width": pix.width,
                "height": pix.height,
                "blocks": blocks,
                "full_text": full_text,
            })

        doc.close()
        return {
            "pages": results,
            "total_pages": len(results),
            "full_text": "\n".join(p["full_text"] for p in results),
        }

    def extract_text(self, file_path: str) -> str:
        """Convenience: extract and return as single string."""
        return self.extract(file_path)["full_text"]
