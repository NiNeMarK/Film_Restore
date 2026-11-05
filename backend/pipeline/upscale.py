"""เพิ่มความละเอียดด้วย Real-ESRGAN x2/x4 (ขั้นที่ 7)

ถ้ายังไม่ติดตั้ง realesrgan/basicsr จะใช้การขยายแบบ Lanczos + unsharp mask แทน
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from ..core.model_manager import ModelUnavailable, get_manager

_enhancers: dict[tuple, object] = {}
_lock = threading.Lock()


def _guard_import(weights):
    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet  # noqa: F401
        from realesrgan import RealESRGANer  # noqa: F401
    except ImportError as exc:
        raise ModelUnavailable(
            "Upscale ด้วย Real-ESRGAN ต้องติดตั้ง realesrgan + basicsr"
        ) from exc
    return weights


get_manager().register("realesrgan_x2plus", _guard_import)
get_manager().register("realesrgan_x4plus", _guard_import)


def _get_enhancer(key: str, device: str, tile: int, half: bool):
    try:
        from realesrgan import RealESRGANer
    except ImportError as exc:
        raise ModelUnavailable(
            "Upscale ด้วย Real-ESRGAN ต้องติดตั้ง realesrgan + basicsr"
        ) from exc

    with _lock:
        cache_key = (key, device, tile, half)
        if cache_key in _enhancers:
            return _enhancers[cache_key]
        manager = get_manager()
        weights = manager.get(key)  # ดาวน์โหลดครั้งแรก + โหลด network
        scale = 2 if key.endswith("x2plus") else 4
        enhancer = RealESRGANer(
            scale=scale,
            model_path=str(weights),
            tile=tile,
            tile_pad=10,
            pre_pad=0,
            half=half,
            device=device,
        )
        _enhancers[cache_key] = enhancer
        return enhancer


def _lanczos(img: np.ndarray, scale: int) -> np.ndarray:
    h, w = img.shape[:2]
    out = cv2.resize(
        img, (w * scale, h * scale), interpolation=cv2.INTER_LANCZOS4
    )
    blurred = cv2.GaussianBlur(out, (0, 0), 1.0)
    return np.clip(out + (out - blurred) * 0.5, 0.0, 1.0)


def upscale(img: np.ndarray, scale: int = 2, tile: int = 0, half: bool = False,
            device: str = "cpu") -> tuple[np.ndarray, str]:
    """คืน (ภาพที่ขยายแล้ว, หมายเหตุ)"""
    scale = 2 if int(scale) not in (2, 4) else int(scale)
    key = "realesrgan_x2plus" if scale == 2 else "realesrgan_x4plus"

    try:
        enhancer = _get_enhancer(key, device, int(tile or 0), bool(half))
    except ModelUnavailable as exc:
        out = _lanczos(img, scale)
        return out, f"Real-ESRGAN ไม่พร้อมใช้ ({exc}) — ใช้ Lanczos x{scale} แทน"

    rgb8 = (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    bgr = rgb8[..., ::-1]
    out_bgr, _ = enhancer.enhance(bgr, outscale=scale)
    h, w = img.shape[:2]
    target = (w * scale, h * scale)
    if out_bgr.shape[1] != target[0] or out_bgr.shape[0] != target[1]:
        out_bgr = cv2.resize(out_bgr, target, interpolation=cv2.INTER_LANCZOS4)
    out = out_bgr[..., ::-1].astype(np.float32) / 255.0
    note = f"Real-ESRGAN x{scale}" + (f" (tile {tile})" if tile else "")
    return np.clip(out, 0.0, 1.0), note
