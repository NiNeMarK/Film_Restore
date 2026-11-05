"""แก้สีซีด/สีเพี้ยนของสไลด์และภาพพิมพ์ + ปรับแต่งขั้นสุดท้าย (ขั้นที่ 3 และ 9)

ทุกฟังก์ชันรับ float32 RGB 0–1 และมีค่า strength (0–1) เพื่อผสมกับภาพเดิม
"""

from __future__ import annotations

import cv2
import numpy as np

_EPS = 1e-6


def blend(original: np.ndarray, edited: np.ndarray, strength: float) -> np.ndarray:
    strength = float(np.clip(strength, 0.0, 1.0))
    return np.clip(original * (1.0 - strength) + edited * strength, 0.0, 1.0)


def gray_world(img: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """ตัดสีเพี้ยนด้วยสมมติฐานว่าเฉลี่ยทุกช่องสีควรเท่ากัน"""
    means = img.reshape(-1, 3).mean(axis=0) + _EPS
    target = float(means.mean())
    gains = target / means
    corrected = np.clip(img * gains, 0.0, 1.0)
    return blend(img, corrected, strength)


def stretch_levels(img: np.ndarray, strength: float = 1.0,
                   clip: tuple[float, float] = (0.5, 99.5)) -> np.ndarray:
    """ยืดฮิสโตแกรมแยกช่องสี (คืนคอนทราสต์และความสดของสีที่ซีดไป)"""
    out = np.empty_like(img)
    for c in range(3):
        lo, hi = np.percentile(img[..., c], clip)
        out[..., c] = np.clip((img[..., c] - lo) / (hi - lo + _EPS), 0.0, 1.0)
    return blend(img, out, strength)


def clahe_luminance(img: np.ndarray, strength: float = 0.5, clip_limit: float = 2.0) -> np.ndarray:
    """เพิ่มคอนทราสต์เฉพาะความสว่าง ไม่แตะสี"""
    lab = cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2LAB)
    l_chan = np.clip(lab[..., 0] * 255.0 / 100.0, 0, 255).astype(np.uint8)
    l_new = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8)).apply(l_chan)
    lab[..., 0] = l_new.astype(np.float32) / 255.0 * 100.0
    out = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0.0, 1.0)
    return blend(img, out, strength)


def boost_saturation(img: np.ndarray, amount: float = 0.2, strength: float = 1.0) -> np.ndarray:
    hsv = cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1] * (1.0 + amount), 0.0, 1.0)
    out = np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), 0.0, 1.0)
    return blend(img, out, strength)


def restore_faded(img: np.ndarray, strength: float = 0.6, mode: str = "faded_color") -> np.ndarray:
    """ฟื้นฟูสีภาพพิมพ์ที่ซีด/สไลด์ที่เพี้ยน

    mode: "faded_color" (ภาพพิมพ์สีซีด) หรือ "slide" (สไลด์ E-6 ที่มักอมแดง)
    """
    if strength <= 0:
        return img
    out = gray_world(img, strength)
    out = stretch_levels(out, strength * 0.9)
    out = clahe_luminance(out, strength * 0.5)
    sat = 0.3 if mode == "faded_color" else 0.18
    out = boost_saturation(out, sat, strength)
    return out


def final_touch(img: np.ndarray, wb: float = 0.3, contrast: float = 0.15,
                saturation: float = 0.1, grain: float = 0.02, seed: int = 7) -> np.ndarray:
    """ขั้นที่ 9: white balance, contrast และเติมเกรนเล็กน้อยให้ดูเป็นธรรมชาติ"""
    out = img
    if wb > 0:
        out = gray_world(out, wb)
    if contrast > 0:
        mid = float(np.median(out.reshape(-1, 3)))
        out = np.clip((out - mid) * (1.0 + contrast) + mid, 0.0, 1.0)
    if saturation > 0:
        out = boost_saturation(out, saturation, 1.0)
    if grain > 0:
        rng = np.random.default_rng(seed)
        noise = rng.normal(0.0, grain, out.shape).astype(np.float32)
        out = np.clip(out + noise, 0.0, 1.0)
    return out
