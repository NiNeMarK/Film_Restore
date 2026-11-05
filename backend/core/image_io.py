"""อ่าน/เขียนภาพ + ครอปขอบฟิล์ม (ขั้นที่ 1 ของ pipeline)

ภาพภายในโปรแกรมใช้ float32 RGB ช่วง 0–1
ไฟล์ 16-bit (TIFF/RAW) จะถูกอ่านเป็น 16-bit แล้วหารด้วย 65535 โดยไม่แปลง gamma
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

RAW_EXTS = {".nef", ".cr2", ".cr3", ".arw", ".dng", ".orf", ".raf", ".rw2", ".pef", ".srw"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".ppm", ".tga"}


def _imread_unicode(path: Path) -> np.ndarray | None:
    """cv2.imread อ่านพาธที่มีอักษรไทยไม่ได้ จึงอ่านเป็น bytes ก่อน"""
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def _to_float(arr: np.ndarray) -> tuple[np.ndarray, int]:
    if arr.dtype == np.uint8:
        return arr.astype(np.float32) / 255.0, 8
    if arr.dtype == np.uint16:
        return arr.astype(np.float32) / 65535.0, 16
    return np.clip(arr.astype(np.float32), 0.0, 1.0), 16


def _to_rgb(arr: np.ndarray) -> np.ndarray:
    img, _ = _to_float(arr)
    if img.ndim == 2:
        img = np.repeat(img[..., None], 3, axis=2)
    elif img.ndim == 3:
        if img.shape[2] == 4:
            img = img[..., :3]
        if img.shape[2] == 1:
            img = np.repeat(img, 3, axis=2)
    if img.shape[2] == 3:
        img = img[..., ::-1]  # BGR -> RGB
    return np.ascontiguousarray(img)


def load_image(path: str | Path) -> tuple[np.ndarray, int]:
    """คืน (ภาพ float32 RGB 0–1, จำนวนบิตต่อช่องของไฟล์ต้นฉบับ)"""
    path = Path(path)
    ext = path.suffix.lower()

    if ext in RAW_EXTS:
        try:
            import rawpy
        except ImportError as exc:
            raise RuntimeError(
                f"อ่านไฟล์ RAW ต้องติดตั้ง rawpy (pip install rawpy) — {path.name}"
            ) from exc
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(half_size=False, no_auto_bright=True, output_bps=16)
        return rgb.astype(np.float32) / 65535.0, 16

    raw = _imread_unicode(path)
    if raw is None:
        raise RuntimeError(f"เปิดไฟล์ภาพไม่ได้: {path}")
    bits = 16 if raw.dtype == np.uint16 else 8
    return _to_rgb(raw), bits


def save_image(path: str | Path, img: np.ndarray, bits: int = 8) -> Path:
    """บันทึกภาพ float32 RGB 0–1 เป็นไฟล์ (รองรับพาธอักษรไทย)"""
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(".png")
    path.parent.mkdir(parents=True, exist_ok=True)

    bgr = np.clip(img, 0.0, 1.0)[..., ::-1]
    if bits == 16:
        arr = (bgr * 65535.0 + 0.5).astype(np.uint16)
    else:
        arr = (bgr * 255.0 + 0.5).astype(np.uint8)
    ok, buf = cv2.imencode(path.suffix, arr)
    if not ok:
        raise RuntimeError(f"เข้ารหัสภาพไม่สำเร็จ: {path}")
    buf.tofile(str(path))
    return path


def resize_max(img: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    """ย่อภาพให้ด้านยาวไม่เกิน max_side คืน (ภาพ, scale ที่ใช้)"""
    h, w = img.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return img, 1.0
    scale = max_side / longest
    small = cv2.resize(
        img, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA
    )
    return small, scale


def is_grayscale(img: np.ndarray, tol: float = 0.02) -> bool:
    spread = np.abs(img.max(axis=2) - img.min(axis=2))
    return float(spread.mean()) < tol


def _uniform_band(mean: np.ndarray, std: np.ndarray, max_px: int, ref: float,
                  uniform_std: float, min_diff: float, band: int) -> int:
    """หาความกว้างของแถบขอบที่เป็นสีเดียวและต่างจากกลางภาพ (ขอบฟิล์ม/ขอบสแกนเนอร์)"""
    n = mean.shape[0]
    cut = 0
    while cut < max_px:
        hi = min(cut + band, n // 2)
        if hi <= cut:
            break
        uniform = float(std[cut:hi].mean()) < uniform_std
        different = abs(float(mean[cut:hi].mean()) - ref) > min_diff
        if uniform and different:
            cut = hi
        else:
            break
    return cut


def crop_film_border(img: np.ndarray, max_frac: float = 0.15) -> np.ndarray:
    """ครอปขอบฟิล์ม/ขอบสแกนที่ติดมา แบบระวังไม่ให้ตัดภาพจริง"""
    h, w = img.shape[:2]
    if h < 64 or w < 64:
        return img

    gray = img.mean(axis=2)
    ref = float(np.median(gray[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]))
    max_y, max_x = int(h * max_frac), int(w * max_frac)

    row_mean, row_std = gray.mean(axis=1), gray.std(axis=1)
    col_mean, col_std = gray.mean(axis=0), gray.std(axis=0)

    kwargs = dict(ref=ref, uniform_std=0.02, min_diff=0.06, band=8)
    top = _uniform_band(row_mean, row_std, max_y, **kwargs)
    bottom = _uniform_band(row_mean[::-1], row_std[::-1], max_y, **kwargs)
    left = _uniform_band(col_mean, col_std, max_x, **kwargs)
    right = _uniform_band(col_mean[::-1], col_std[::-1], max_x, **kwargs)

    if top + bottom >= h * 0.5 or left + right >= w * 0.5:
        return img
    if not any((top, bottom, left, right)):
        return img
    return np.ascontiguousarray(img[top : h - bottom, left : w - right])
