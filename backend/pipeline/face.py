"""ฟื้นฟูใบหน้าด้วย GFPGAN พร้อมตัวปรับ fidelity (ขั้นที่ 8)

- fidelity 0 = เน้นความสวย/สมจริงของโมเดล, 1 = เน้นเหมือนต้นฉบับ
  (ส่งต่อไปเป็น weight ของ GFPGAN ซึ่งยิ่งสูงยิ่งเหมือนต้นฉบับ)
- ถ้าต้องการ CodeFormer ให้ติดตั้ง repo ของ CodeFormer แล้วสลับใน `restore_faces()`
  (แผนกำหนด CodeFormer เป็นโมเดลหลัก แต่ตัวนั้นต้องติดตั้งจาก GitHub ไม่มีใน PyPI)
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from ..core.model_manager import ModelUnavailable, get_manager

_restorers: dict[tuple, object] = {}
_lock = threading.Lock()


def _loader(weights):
    try:
        from gfpgan import GFPGANer  # noqa: F401
    except ImportError as exc:
        raise ModelUnavailable(
            "ฟื้นฟูใบหน้าด้วย GFPGAN ต้องติดตั้ง gfpgan (pip install gfpgan)"
        ) from exc
    return weights


get_manager().register("gfpgan_v14", _loader)


def _get_restorer(device: str):
    try:
        from gfpgan import GFPGANer
    except ImportError as exc:
        raise ModelUnavailable(
            "ฟื้นฟูใบหน้าด้วย GFPGAN ต้องติดตั้ง gfpgan (pip install gfpgan)"
        ) from exc

    with _lock:
        if device in _restorers:
            return _restorers[device]
        manager = get_manager()
        weights = manager.get("gfpgan_v14")
        restorer = GFPGANer(
            model_path=str(weights),
            upscale=1,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=None,
            device=device,
        )
        _restorers[device] = restorer
        return restorer


def restore_faces(img: np.ndarray, fidelity: float = 0.7, device: str = "cpu"):
    """คืน (ภาพ, หมายเหตุ) — ถ้าไม่พบใบหน้าจะคืนภาพเดิม"""
    fidelity = float(np.clip(fidelity, 0.0, 1.0))
    restorer = _get_restorer(device)

    bgr = (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)[..., ::-1]
    _, _, restored = restorer.enhance(
        bgr,
        has_aligned=False,
        only_center_face=False,
        paste_back=True,
        weight=fidelity,
    )
    if restored is None:
        return img, "ไม่พบใบหน้าในภาพ — ข้ามขั้นฟื้นฟูใบหน้า"

    if restored.shape[:2] != img.shape[:2]:
        restored = cv2.resize(restored, (img.shape[1], img.shape[0]),
                              interpolation=cv2.INTER_LANCZOS4)
    out = restored[..., ::-1].astype(np.float32) / 255.0
    return np.clip(out, 0.0, 1.0), f"GFPGAN v1.4 (fidelity {fidelity:.2f})"
