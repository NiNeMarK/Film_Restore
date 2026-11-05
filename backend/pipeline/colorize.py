"""ใส่สีให้ภาพขาวดำด้วย DDColor (ขั้นที่ 6)

ตามแผนข้อ 10 (ความเสี่ยงภาพความละเอียดสูง): ใส่สีบนภาพย่อ แล้วขยายช่องสี (chroma)
กลับขึ้นไปทับความสว่าง (luma) ของภาพต้นฉบับ เพื่อลดเวลาและรักษารายละเอียด
"""

from __future__ import annotations

import cv2
import numpy as np

from ..core.model_manager import ModelUnavailable

DDCOLOR_MODEL = "damo/cv_ddcolor_image-colorization"
_colorizer: dict[str, object] = {}


def _require_modelscope():
    try:
        from modelscope.pipelines import pipeline  # noqa: F401
        from modelscope.utils.constant import Tasks  # noqa: F401
    except ImportError as exc:
        raise ModelUnavailable(
            "ใส่สีด้วย DDColor ต้องติดตั้ง modelscope (pip install modelscope)"
        ) from exc


def _get_colorizer(device: str):
    _require_modelscope()
    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks

    if device not in _colorizer:
        _colorizer[device] = pipeline(
            Tasks.image_colorization,
            model=DDCOLOR_MODEL,
            device="gpu" if device.startswith("cuda") else "cpu",
        )
    return _colorizer[device]


def _to_u8_bgr(img: np.ndarray) -> np.ndarray:
    rgb = (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    return rgb[..., ::-1]


def colorize(img: np.ndarray, strength: float = 0.8, max_side: int = 1024,
             device: str = "cpu") -> tuple[np.ndarray, str]:
    """คืน (ภาพที่ใส่สีแล้ว, หมายเหตุ) — โยน ModelUnavailable เมื่อยังไม่มีโมเดล"""
    strength = float(np.clip(strength, 0.0, 1.0))
    pipe = _get_colorizer(device)
    h, w = img.shape[:2]

    scale = min(1.0, max_side / max(h, w))
    small = img if scale >= 1.0 else cv2.resize(
        img, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA
    )

    result = pipe(_to_u8_bgr(small))
    colored = result["output_img"] if isinstance(result, dict) else result
    colored = np.asarray(colored)
    if colored.ndim == 2:
        colored = cv2.cvtColor(colored, cv2.COLOR_GRAY2BGR)

    if colored.shape[:2] != (h, w):
        colored = cv2.resize(colored, (w, h), interpolation=cv2.INTER_CUBIC)

    base = cv2.cvtColor(_to_u8_bgr(img), cv2.COLOR_BGR2YCrCb)
    tint = cv2.cvtColor(colored.astype(np.uint8), cv2.COLOR_BGR2YCrCb)
    base[..., 1:] = (
        base[..., 1:].astype(np.float32) * (1.0 - strength)
        + tint[..., 1:].astype(np.float32) * strength
    ).round().clip(0, 255).astype(np.uint8)

    out = cv2.cvtColor(base, cv2.COLOR_YCrCb2BGR)[..., ::-1].astype(np.float32) / 255.0
    note = f"DDColor บนภาพย่อ {small.shape[1]}×{small.shape[0]} แล้วขยายช่องสีกลับ"
    if strength < 0.999:
        note += f" (ความแรง {strength:.2f})"
    return np.clip(out, 0.0, 1.0), note
