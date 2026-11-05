"""ลบรอยขีดข่วน ฝุ่น และรอยพับ (ขั้นที่ 4)

- ตรวจรอยด้วย morphological top-hat / black-hat (รอยเส้นบางและจุดสว่าง-มืด)
- ซ่อมด้วย OpenCV inpainting หรือ LaMa ถ้าติดตั้ง simple-lama-inpainting
"""

from __future__ import annotations

import cv2
import numpy as np

from ..core.model_manager import ModelUnavailable

_lama_cache: dict[str, object] = {}


def _to_u8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def detect_defects(img: np.ndarray, sensitivity: float = 0.5,
                   max_area_frac: float = 0.05) -> np.ndarray:
    """คืน mask uint8 0/255 ของตำแหน่งที่น่าจะเสียหาย

    เก็บเฉพาะองค์ประกอบที่ "บาง" (รอยขีดข่วน/ฝุ่น) ไม่ใช่ก้อนใหญ่ (ขอบวัตถุ/ใบหน้า)
    """
    gray = cv2.cvtColor(_to_u8(img), cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    size = 7 if min(h, w) > 800 else 5
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    black_hat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)  # เส้นดำบาง
    top_hat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)      # จุด/เส้นสว่าง
    response = cv2.max(black_hat, top_hat)

    percentile = 99.6 - 2.6 * float(np.clip(sensitivity, 0.0, 1.0))
    threshold = max(float(np.percentile(response, percentile)), 18.0)
    mask = np.where(response >= threshold, 255, 0).astype(np.uint8)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    max_area = max(16, int(max_area_frac * h * w))
    clean = np.zeros_like(mask)
    for idx in range(1, count):
        _, _, width, height, area = stats[idx]
        if area < 4 or area > max_area:
            continue
        long_side = max(width, height)
        short_side = max(1, min(width, height))
        # ความหนาเฉลี่ย = พื้นที่ / ด้านยาว → รอยขีดข่วนบาง แต่ก้อนใหญ่จะหนา
        thickness = area / max(1, long_side)
        elongated = long_side / short_side >= 2.5
        if thickness <= 4.0 or (elongated and thickness <= 6.0):
            clean[labels == idx] = 255

    if clean.any():
        clean = cv2.dilate(clean, np.ones((3, 3), np.uint8), iterations=1)
    return clean


def _lama(device: str):
    """โหลด LaMa ครั้งแรกเท่านั้น (weights จัดการโดยไลบรารี)"""
    if device not in _lama_cache:
        try:
            from simple_lama_inpainting import SimpleLama
        except ImportError as exc:
            raise ModelUnavailable(
                "ลบรอยด้วย LaMa ต้องติดตั้ง simple-lama-inpainting"
            ) from exc
        try:
            import torch

            target = torch.device(device)
        except ImportError:
            target = device
        _lama_cache[device] = SimpleLama(device=target)
    return _lama_cache[device]


def _inpaint_lama(img: np.ndarray, mask: np.ndarray, device: str) -> np.ndarray:
    from PIL import Image

    lama = _lama(device)
    image = Image.fromarray(_to_u8(img))
    mask_img = Image.fromarray(mask)
    result = lama(image, mask_img)
    return np.asarray(result.convert("RGB"), dtype=np.float32) / 255.0


def remove_scratches(img: np.ndarray, sensitivity: float = 0.5, strength: float = 0.7,
                     use_lama: bool = True, device: str = "cpu") -> tuple[np.ndarray, np.ndarray, str]:
    """คืน (ภาพที่ซ่อมแล้ว, mask, หมายเหตุ)"""
    mask = detect_defects(img, sensitivity=sensitivity)
    if not mask.any():
        return img, mask, "ไม่พบรอยที่ต้องซ่อม"

    coverage = float(mask.mean()) / 255.0
    if coverage > 0.10:
        return (
            img,
            mask,
            f"ตรวจพบพื้นที่น่าสงสัย {coverage * 100:.1f}% มากเกินไป — ข้ามการซ่อม "
            "(ลดความไวหรือปิดขั้นลบรอย)",
        )

    repaired = None
    note = ""
    if use_lama and coverage > 0.0005:
        try:
            repaired = _inpaint_lama(img, mask, device)
            note = f"ซ่อมด้วย LaMa ({coverage * 100:.2f}% ของภาพ)"
        except ModelUnavailable:
            repaired = None
        except Exception as exc:
            note = f"LaMa ใช้ไม่ได้ ({exc}) — เปลี่ยนไปใช้ OpenCV"
            repaired = None

    if repaired is None:
        bgr = _to_u8(img)[..., ::-1]
        fixed = cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)
        repaired = fixed[..., ::-1].astype(np.float32) / 255.0
        note = note or f"ซ่อมด้วย OpenCV inpainting ({coverage * 100:.2f}% ของภาพ)"

    m = mask[..., None].astype(np.float32) / 255.0
    blended = img * (1.0 - m) + repaired * m
    amount = float(np.clip(strength, 0.0, 1.0))
    out = img * (1.0 - amount) + blended * amount
    return np.clip(out, 0.0, 1.0), mask, note
