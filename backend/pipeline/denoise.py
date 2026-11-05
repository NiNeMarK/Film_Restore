"""ลดนอยส์และเกรนแต่เก็บรายละเอียดไว้ (ขั้นที่ 5)

ใช้ Non-local Means ของ OpenCV เป็นแกน แล้วเติมรายละเอียดความถี่สูงกลับบางส่วน
เพื่อไม่ให้ภาพดูพลาสติก ถ้าติดตั้ง SCUNet ในอนาคตสามารถสลับมาใช้แทนได้ที่ `denoise()`
"""

from __future__ import annotations

import cv2
import numpy as np


def _to_u8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def denoise(img: np.ndarray, strength: float = 0.5,
            preserve_detail: float = 0.35) -> tuple[np.ndarray, str]:
    """strength 0–1: 0 = ปิด, 1 = ลดแรงสุด"""
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength <= 0:
        return img, "ข้ามขั้นลดเกรน"

    h = int(round(2 + 10 * strength))
    bgr = _to_u8(img)[..., ::-1]
    smoothed = cv2.fastNlMeansDenoisingColored(bgr, None, h, h, 7, 21)
    out = smoothed[..., ::-1].astype(np.float32) / 255.0

    if preserve_detail > 0:
        low = cv2.GaussianBlur(img, (0, 0), 1.2)
        high = img - low
        out = np.clip(out + high * preserve_detail, 0.0, 1.0)

    h_px, w_px = img.shape[:2]
    note = f"NLM h={h}, เก็บรายละเอียด {int(preserve_detail * 100)}%"
    if h_px * w_px > 4_000_000:
        note += " — ภาพใหญ่ใช้เวลาหลายวินาทีบน CPU"
    return out, note
