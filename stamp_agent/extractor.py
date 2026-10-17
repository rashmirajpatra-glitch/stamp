from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import fitz
import numpy as np

from stamp_agent.models import BoundingBox, ExtractionFinding

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _read_pages(input_file: str | Path) -> list[np.ndarray]:
    path = Path(input_file)
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_IMAGE_EXTENSIONS:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Failed to read image: {path}")
        return [image]

    if suffix == ".pdf":
        pages: list[np.ndarray] = []
        doc = fitz.open(str(path))
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            buf = np.frombuffer(pix.samples, dtype=np.uint8)
            channels = 4 if pix.alpha else 3
            arr = buf.reshape(pix.height, pix.width, channels)
            if channels == 4:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            else:
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            pages.append(arr)
        return pages

    raise ValueError(f"Unsupported input format: {suffix}. Use JPG/PNG/PDF.")


def _dominant_color_name(region_bgr: np.ndarray) -> str:
    hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
    mean_hue = float(np.mean(hsv[:, :, 0]))
    mean_sat = float(np.mean(hsv[:, :, 1]))
    if mean_sat < 30:
        return "gray/black"
    if mean_hue < 10 or mean_hue > 160:
        return "red"
    if 90 <= mean_hue <= 130:
        return "blue"
    if 35 <= mean_hue <= 85:
        return "green"
    return "other"


def _extract_stamp_candidates(image: np.ndarray, page: int) -> list[ExtractionFinding]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    red1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
    red2 = cv2.inRange(hsv, (160, 70, 50), (179, 255, 255))
    blue = cv2.inRange(hsv, (90, 70, 50), (130, 255, 255))
    green = cv2.inRange(hsv, (35, 70, 50), (85, 255, 255))

    mask = red1 | red2 | blue | green
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    findings: list[ExtractionFinding] = []
    page_height, page_width = image.shape[:2]

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 500:
            continue

        peri = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area / (peri * peri)) if peri > 0 else 0.0
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / float(h or 1)

        if circularity < 0.3 and not (0.6 <= aspect_ratio <= 1.8):
            continue

        roi = image[y : y + h, x : x + w]
        color_name = _dominant_color_name(roi)
        confidence = min(0.99, 0.45 + circularity * 0.45 + min(area / 10000, 0.1))

        findings.append(
            ExtractionFinding(
                finding_type="stamp_or_seal",
                bbox=BoundingBox(x=x, y=y, width=w, height=h),
                area=float(area),
                confidence=float(round(confidence, 4)),
                color=color_name,
                page=page,
                metadata={
                    "circularity": round(float(circularity), 4),
                    "aspect_ratio": round(float(aspect_ratio), 4),
                    "page_width": page_width,
                    "page_height": page_height,
                    "center_x_ratio": round((x + w / 2) / float(page_width or 1), 4),
                    "center_y_ratio": round((y + h / 2) / float(page_height or 1), 4),
                },
            )
        )

    return findings


def _extract_signature_candidates(image: np.ndarray, page: int) -> list[ExtractionFinding]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    page_height, page_width = gray.shape
    findings: list[ExtractionFinding] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 200:
            continue

        x, y, bw, bh = cv2.boundingRect(contour)
        aspect_ratio = bw / float(bh or 1)
        page_position_ratio = y / float(page_height or 1)

        if aspect_ratio < 2.0 or bh > page_height * 0.25 or bw < page_width * 0.05:
            continue

        roi = thresh[y : y + bh, x : x + bw]
        stroke_density = float(np.count_nonzero(roi)) / float(roi.size or 1)
        if not 0.05 <= stroke_density <= 0.55:
            continue

        confidence = min(0.98, 0.4 + stroke_density + (0.2 if page_position_ratio > 0.55 else 0.0))
        findings.append(
            ExtractionFinding(
                finding_type="signature",
                bbox=BoundingBox(x=x, y=y, width=bw, height=bh),
                area=float(area),
                confidence=float(round(confidence, 4)),
                color="dark_ink",
                page=page,
                metadata={
                    "stroke_density": round(stroke_density, 4),
                    "aspect_ratio": round(float(aspect_ratio), 4),
                    "page_position_ratio": round(page_position_ratio, 4),
                    "page_width": page_width,
                    "page_height": page_height,
                    "center_x_ratio": round((x + bw / 2) / float(page_width or 1), 4),
                    "center_y_ratio": round((y + bh / 2) / float(page_height or 1), 4),
                },
            )
        )

    return findings


def attach_seal_text(findings: list[ExtractionFinding], sarvam_result: dict[str, Any] | None) -> None:
    if not sarvam_result:
        return

    lines: list[str] = []
    pages = sarvam_result.get("document", {}).get("pages", [])
    for page in pages:
        for line in page.get("lines", []):
            if isinstance(line, dict):
                txt = line.get("text")
                if txt:
                    lines.append(str(txt))

    joined = " | ".join(lines[:12])
    if not joined:
        return

    for finding in findings:
        if finding.finding_type == "stamp_or_seal":
            finding.text = joined


def extract_stamps_seals_signatures(
    input_file: str | Path,
    sarvam_result: dict[str, Any] | None = None,
) -> list[ExtractionFinding]:
    pages = _read_pages(input_file)
    all_findings: list[ExtractionFinding] = []

    for idx, page in enumerate(pages, start=1):
        all_findings.extend(_extract_stamp_candidates(page, page=idx))
        all_findings.extend(_extract_signature_candidates(page, page=idx))

    attach_seal_text(all_findings, sarvam_result)

    logger.info("Extracted %d findings from %s", len(all_findings), input_file)
    return all_findings
