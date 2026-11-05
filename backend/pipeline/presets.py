"""ค่าเริ่มต้นของแต่ละประเภทฟิล์ม (ตามแผนข้อ 3.1 และ 7.2)

ทุกค่าเปิด/ปิดและปรับความแรงได้จาก UI — ไฟล์นี้เป็นเพียงค่าเริ่มต้นของโหมด
"""

from __future__ import annotations

from copy import deepcopy

# ค่ากลางที่ทุกโหมดใช้ร่วมกัน (ขั้นสุดท้าย + ความแรงเริ่มต้น)
_BASE: dict = dict(
    invert_gamma=1.0,
    final_wb=0.3,
    final_contrast=0.15,
    final_saturation=0.1,
    final_grain=0.02,
)

PRESETS: dict[str, dict] = {
    "bw_negative": {
        **_BASE,
        "invert": "bw",
        "color_fix": False,
        "color_fix_strength": 0.5,
        "scratch": True,
        "scratch_strength": 0.7,
        "denoise": 0.6,
        "colorize": True,
        "colorize_strength": 0.8,
        "upscale": 2,
        "face": 0.7,
    },
    "color_negative": {
        **_BASE,
        "invert": "color",
        "color_fix": True,
        "color_fix_strength": 0.5,
        "scratch": True,
        "scratch_strength": 0.6,
        "denoise": 0.5,
        "colorize": False,
        "colorize_strength": 0.8,
        "upscale": 2,
        "face": 0.7,
    },
    "slide": {
        **_BASE,
        "invert": None,
        "color_fix": True,
        "color_fix_strength": 0.6,
        "scratch": True,
        "scratch_strength": 0.5,
        "denoise": 0.4,
        "colorize": False,
        "colorize_strength": 0.8,
        "upscale": 2,
        "face": 0.7,
    },
    "bw_print": {
        **_BASE,
        "invert": None,
        "color_fix": False,
        "color_fix_strength": 0.5,
        "scratch": True,
        "scratch_strength": 0.8,
        "denoise": 0.5,
        "colorize": True,
        "colorize_strength": 0.8,
        "upscale": 2,
        "face": 0.7,
    },
    "faded_color": {
        **_BASE,
        "invert": None,
        "color_fix": True,
        "color_fix_strength": 0.7,
        "scratch": True,
        "scratch_strength": 0.6,
        "denoise": 0.4,
        "colorize": False,
        "colorize_strength": 0.8,
        "upscale": 2,
        "face": 0.7,
    },
}

PRESET_LABELS: dict[str, str] = {
    "bw_negative": "เนกาทีฟขาวดำ",
    "color_negative": "เนกาทีฟสี (C-41)",
    "slide": "สไลด์ / โพสิตีฟ (E-6)",
    "bw_print": "ภาพพิมพ์ขาวดำ",
    "faded_color": "ภาพพิมพ์สีที่ซีด",
}

PRESET_NOTES: dict[str, str] = {
    "bw_negative": "กลับสี + ลบรอย + ลดเกรน + ใส่สี + upscale/หน้า",
    "color_negative": "กลับสีแบบตัดสีส้มฐานฟิล์ม + แก้สี + ลบรอย + ลดเกรน",
    "slide": "แก้สีที่ซีด/เพี้ยนแดง + ลบรอย + ลดเกรน",
    "bw_print": "ลบรอยพับ/รอยฉีก + ลดเกรน + ใส่สี",
    "faded_color": "ฟื้นฟูสีที่ซีด + ลบรอย + ลดเกรน",
}

# ค่าที่ผู้ใช้แก้จาก UI/API ได้ (กันคีย์แปลกปลอมจาก JSON)
EDITABLE_KEYS: tuple[str, ...] = tuple(PRESETS["color_negative"].keys())


def get_preset(name: str) -> dict:
    if name not in PRESETS:
        raise KeyError(f"ไม่รู้จักโหมด '{name}' (มี: {', '.join(PRESETS)})")
    return deepcopy(PRESETS[name])
