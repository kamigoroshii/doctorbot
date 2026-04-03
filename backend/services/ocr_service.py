import cv2
import numpy as np
import pytesseract
import io
import subprocess
import os
import re
from PIL import Image, ImageFilter, ImageEnhance
from typing import List

class OCRService:
    OCR_HINT_TERMS = [
        "rx", "prescription", "mg", "ml", "tab", "capsule", "tablet", "daily",
        "od", "bd", "bid", "tid", "qid", "hs", "amoxicillin", "ibuprofen",
        "omeprazole", "metformin", "lisinopril", "atorvastatin", "cetirizine",
        "paracetamol", "aspirin", "azithromycin", "ciprofloxacin", "diclofenac",
        "pantoprazole", "amlodipine", "losartan", "glimepiride", "metoprolol",
    ]

    def __init__(self):
        self.tesseract_available = self._setup_tesseract()
        if self.tesseract_available:
            print("✅ Tesseract OCR initialized successfully")
        else:
            print("⚠️ Tesseract not found, will use fallback methods")

    def _setup_tesseract(self) -> bool:
        possible_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe",
            r"C:\Users\ADMIN\AppData\Local\Tesseract-OCR\tesseract.exe",
            "tesseract"
        ]
        print("🔍 Searching for Tesseract installation...")
        for path in possible_paths:
            try:
                if path == "tesseract":
                    subprocess.run(['tesseract', '--version'], capture_output=True, check=True)
                    print("✅ Found Tesseract in PATH")
                    return True
                else:
                    print(f"   Checking: {path}")
                    if os.path.exists(path):
                        subprocess.run([path, '--version'], capture_output=True, check=True)
                        pytesseract.pytesseract.tesseract_cmd = path
                        print(f"✅ Found Tesseract at: {path}")
                        return True
                    else:
                        print(f"   ❌ Not found: {path}")
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                print(f"   ❌ Error testing {path}: {str(e)}")
                continue
        print("❌ Tesseract not found in any common locations")
        return False

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    async def extract_text(self, image_data: bytes) -> str:
        """Extract text from prescription image using Tesseract OCR."""
        try:
            if self.tesseract_available:
                return await self._tesseract_ocr(image_data)
            else:
                print("📋 Tesseract not available, using sample prescription...")
                return self._get_sample_prescription()
        except Exception as e:
            print(f"⚠️ OCR failed: {str(e)}, using sample prescription")
            return self._get_sample_prescription()

    # ------------------------------------------------------------------
    # INTERNAL OCR
    # ------------------------------------------------------------------

    async def _tesseract_ocr(self, image_data: bytes) -> str:
        """Try many preprocessing strategies and pick the best OCR result."""
        print("📸 Processing image with Tesseract OCR...")

        # Build image variants
        variants = self._build_image_variants(image_data)

        # Only 2 Tesseract configs — PSM 4 (single column) and PSM 6 (block)
        # This gives quality coverage without the 40-run overhead
        ocr_configs = [
            r'--oem 3 --psm 4',   # single column ← best for prescriptions
            r'--oem 3 --psm 6',   # uniform block
        ]

        candidates: List[str] = []
        for variant_name, variant_img in variants:
            for config in ocr_configs:
                try:
                    raw = pytesseract.image_to_string(variant_img, config=config)
                    cleaned = self._clean_extracted_text(raw)
                    if cleaned:
                        candidates.append(cleaned)
                except Exception:
                    continue

        result_text = self._select_best_ocr_result(candidates)

        if result_text.strip():
            print(f"✅ Tesseract extracted {len(result_text.splitlines())} lines of text")
            return result_text

        # Absolute fallback: try the raw PIL image with no preprocessing
        try:
            pil_img = Image.open(io.BytesIO(image_data))
            raw_fallback = pytesseract.image_to_string(pil_img, config=r'--oem 3 --psm 4')
            if raw_fallback.strip():
                cleaned = self._clean_extracted_text(raw_fallback)
                score = self._score_ocr_text(cleaned)
                print(f"⚠️  Raw PIL fallback OCR score: {score}")
                if score > 0:
                    return cleaned
        except Exception as fb_err:
            print(f"⚠️  Raw PIL fallback failed: {fb_err}")

        print("⚠️  No meaningful text extracted – image quality is too low for OCR")
        return "__OCR_FAILED__"

    def _build_image_variants(self, image_data: bytes) -> List[tuple]:
        """
        Return the 4 most effective image preprocessing variants.
        Ordered: best-first to fail-fast if early variants work well.
        Target: ~8 Tesseract runs total (4 variants × 2 PSM modes).
        """
        variants = []
        try:
            pil_original = Image.open(io.BytesIO(image_data)).convert("RGB")
            w, h = pil_original.size

            # ── Variant 1: PIL 2× + sharpen + contrast boost ──────────────
            # Best general-purpose variant; handles most legible prescriptions.
            resized = pil_original.resize((w * 2, h * 2), Image.LANCZOS)
            sharpened = resized.filter(ImageFilter.SHARPEN)
            gray_pil = ImageEnhance.Contrast(sharpened.convert("L")).enhance(2.0)
            variants.append(("pil_contrast_2x", np.array(gray_pil)))

            arr = np.frombuffer(image_data, dtype=np.uint8)
            cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if cv_img is not None:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                gray2x = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))

                # ── Variant 2: Adaptive threshold 2× ──────────────────────
                # Best for handwritten text on uneven paper.
                clahe_img = clahe.apply(gray2x)
                blurred = cv2.GaussianBlur(clahe_img, (3, 3), 0)
                adaptive = cv2.adaptiveThreshold(
                    blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY, 15, 10
                )
                variants.append(("cv_adaptive_2x", adaptive))

                # ── Variant 3: CLAHE 2× raw (no binarisation) ─────────────
                # Good for faint ink / light handwriting.
                variants.append(("cv_clahe_2x", clahe_img))

                # ── Variant 4: Deskew + Otsu ──────────────────────────────
                # Handles rotated/angled photos.
                deskewed = self._deskew_image(cv_img)
                gray_desk = cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY)
                gray_desk2x = cv2.resize(gray_desk, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
                clahe_desk = clahe.apply(gray_desk2x)
                _, otsu_desk = cv2.threshold(
                    clahe_desk, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )
                variants.append(("cv_deskew_otsu_2x", otsu_desk))

        except Exception as e:
            print(f"⚠️  Image variant generation failed: {e}")

        return variants

    def _deskew_image(self, image: np.ndarray) -> np.ndarray:
        """Deskew image based on text orientation."""
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            inverted = cv2.bitwise_not(gray)
            coords = np.column_stack(np.where(inverted > 0))
            if coords.size == 0:
                return image
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = 90 + angle
            if abs(angle) < 1.0:
                return image
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            return cv2.warpAffine(image, matrix, (width, height),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        except Exception:
            return image

    def _clean_extracted_text(self, extracted_text: str) -> str:
        """Normalize OCR text and keep only meaningful lines."""
        cleaned_lines = []
        for line in extracted_text.split('\n'):
            line = " ".join(line.strip().split())
            if len(line) > 2:
                cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)

    def _score_ocr_text(self, text: str) -> int:
        """
        Heuristic score for choosing the most plausible OCR output.
        Higher = more likely to be real prescription text.
        """
        if not text:
            return 0

        lowered = text.lower()
        score = 0

        # Base: length (capped to avoid rewarding pure noise volume)
        score += min(len(text), 200)

        # Strong medical signals
        score += len(re.findall(r'\d+\s*(?:mg|ml|mcg|iu|g)\b', lowered)) * 50
        score += len(re.findall(r'\b(?:od|bd|bid|tid|qid|hs|daily|nocte)\b', lowered)) * 40
        score += len(re.findall(r'\b(?:capsule|tablet|cap|tab|syrup|drops|injection)\b', lowered)) * 30
        score += sum(30 for term in self.OCR_HINT_TERMS if term in lowered)

        # Readable word ratio — the key quality signal
        tokens = re.findall(r'[A-Za-z]{3,}', text)
        if tokens:
            readable = sum(1 for t in tokens if re.search(r'[aeiouAEIOU]', t))
            ratio = readable / len(tokens)
            if ratio >= 0.55:
                score += int(readable * 10)   # clean text bonus
            elif ratio >= 0.35:
                score += int(readable * 4)    # partial readability
            else:
                # Consonant soup — heavy penalty (typical Tesseract hallucination)
                score -= int((len(tokens) - readable) * 12)

        # Symbol noise penalty
        noisy = len(re.findall(r'[^A-Za-z0-9\s,.:/()|\-]', text))
        score -= noisy * 4

        return score

    def _select_best_ocr_result(self, candidates: List[str]) -> str:
        """Return highest-scoring OCR candidate. Returns '' if all are noise (<10)."""
        if not candidates:
            return ""
        best = max(candidates, key=self._score_ocr_text)
        best_score = self._score_ocr_text(best)
        print(f"📊 OCR best score: {best_score} (from {len(candidates)} candidates)")
        if best_score < 10:
            print("⚠️  All OCR candidates are noise (score < 10)")
            return ""
        return best

    def _get_sample_prescription(self) -> str:
        """Return sample prescription for testing/demo."""
        return """
Dr. Sarah Johnson, MD
Family Medicine Clinic

Patient: John Smith
Date: December 20, 2024

Prescription:

1. Amoxicillin 500mg - Take 1 tablet BD for 7 days
2. Paracetamol 650mg - Take 1 tablet TID PRN fever
3. Omeprazole 20mg - Take 1 capsule OD before breakfast

Dr. Sarah Johnson
License: MD12345
        """.strip()

    def enhance_image_quality(self, image: np.ndarray) -> np.ndarray:
        """Additional image enhancement (kept for compatibility)."""
        try:
            enhanced = cv2.convertScaleAbs(image, alpha=1.2, beta=10)
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            sharpened = cv2.filter2D(enhanced, -1, kernel)
            return cv2.fastNlMeansDenoising(sharpened)
        except Exception as e:
            print(f"⚠️ Image enhancement failed: {str(e)}")
            return image