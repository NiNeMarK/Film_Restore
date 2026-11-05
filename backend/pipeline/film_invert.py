"""กลับสีเนกาทีฟ + ตัดสีส้มของฐานฟิล์ม

สูตรตามแผนข้อ 7.1: ความหนาแน่นเหนือฐานฟิล์ม (density) = log10(base / img)
แล้วยืดแต่ละช่องสีแยกกันเพื่อให้ได้ color balance ที่ถูกต้อง
"""

from __future__ import annotations

import numpy as np


def srgb_to_linear(img: np.ndarray) -> np.ndarray:
    img = np.clip(img, 0.0, 1.0)
    return np.where(img <= 0.04045, img / 12.92, ((img + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(img: np.ndarray) -> np.ndarray:
    img = np.clip(img, 0.0, 1.0)
    return np.where(img <= 0.0031308, img * 12.92, 1.055 * img ** (1 / 2.4) - 0.055)


def detect_film_base(img: np.ndarray) -> np.ndarray:
    """หาสีฐานฟิล์ม (ส่วนที่ไม่ถูกแสง) จากขอบภาพ ซึ่งเป็นส่วนที่สว่างที่สุดในเนกาทีฟ"""
    h, w = img.shape[:2]
    m = max(h, w) // 40
    border = np.concatenate(
        [
            img[:m].reshape(-1, 3),
            img[-m:].reshape(-1, 3),
            img[:, :m].reshape(-1, 3),
            img[:, -m:].reshape(-1, 3),
        ]
    )
    return np.percentile(border, 99, axis=0)


def invert_color_negative(
    img: np.ndarray, base=None, gamma: float = 1.0, clip=(0.1, 99.9)
) -> np.ndarray:
    """img: float32 RGB 0-1 (ควรสแกนเป็น 16-bit linear)"""
    img = np.clip(img, 1e-6, 1.0)
    base = detect_film_base(img) if base is None else np.asarray(base, dtype=np.float32)
    base = np.clip(base, 1e-6, 1.0)
    density = np.log10(base / img)  # ความหนาแน่นเหนือฐานฟิล์ม = ตัดสีส้มออก
    out = np.empty_like(density)
    for c in range(3):  # ยืดแต่ละช่องสีแยกกัน = แก้ color balance
        lo, hi = np.percentile(density[..., c], clip)
        out[..., c] = (density[..., c] - lo) / (hi - lo + 1e-6)
    return np.clip(out, 0, 1) ** (1 / gamma)


def invert_bw_negative(img: np.ndarray, clip=(0.1, 99.9)) -> np.ndarray:
    gray = img.mean(axis=2) if img.ndim == 3 else img
    pos = 1.0 - gray
    lo, hi = np.percentile(pos, clip)
    return np.clip((pos - lo) / (hi - lo + 1e-6), 0, 1)


def invert(img: np.ndarray, mode: str = "color", gamma: float = 1.0) -> np.ndarray:
    """mode: "color" (C-41) หรือ "bw" (เนกาทีฟขาวดำ)"""
    if mode == "bw":
        gray = invert_bw_negative(img)
        return np.repeat(gray[..., None], 3, axis=2)
    return invert_color_negative(img, gamma=gamma)
