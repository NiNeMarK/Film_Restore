"""Pipeline Engine — ร้อยแต่ละขั้นตาม preset (ขั้นที่ 2–9 ของแผน)

ลำดับขั้น: กลับสี -> แก้สี -> ลบรอย -> ลดเกรน -> ใส่สี -> upscale -> ฟื้นฟูใบหน้า -> ปรับแต่งขั้นสุดท้าย
ทุกขั้นปิดได้ และถ้าโมเดลยังไม่พร้อมจะข้ามขั้นนั้นพร้อมบันทึกคำเตือนไว้ ไม่ทำให้ทั้งงานล้ม
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from ..core import gpu as gpu_mod
from ..core.image_io import is_grayscale
from ..core.model_manager import ModelUnavailable
from . import color_fix, colorize, denoise, face, film_invert, presets, scratch, upscale

ProgressFn = Optional[Callable[[float, str], None]]

DEFAULT_MAX_PIXELS = int(os.environ.get("FILM_RESTORE_MAX_PIXELS", 30_000_000))


@dataclass
class Stage:
    key: str
    label: str
    image: np.ndarray
    seconds: float
    note: str = ""

    def as_dict(self) -> dict:
        h, w = self.image.shape[:2]
        return {
            "key": self.key,
            "label": self.label,
            "width": w,
            "height": h,
            "seconds": self.seconds,
            "note": self.note,
        }


@dataclass
class RunResult:
    preset: str
    settings: dict
    meta: dict
    stages: list[Stage]
    warnings: list[str] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def image(self) -> np.ndarray | None:
        return self.stages[-1].image if self.stages else None

    def as_dict(self) -> dict:
        return {
            "preset": self.preset,
            "preset_label": presets.PRESET_LABELS.get(self.preset, self.preset),
            "settings": self.settings,
            "meta": self.meta,
            "stages": [stage.as_dict() for stage in self.stages],
            "warnings": self.warnings,
            "elapsed": round(self.elapsed, 2),
        }


def resolve_settings(preset: str, overrides: dict | None = None,
                     source_bits: int = 8) -> dict:
    settings = presets.get_preset(preset)
    for key, value in (overrides or {}).items():
        if key not in presets.EDITABLE_KEYS:
            continue
        # None/False หมายถึง "ปิดขั้นนี้" (ใช้กับ invert และ face ที่เป็นค่าว่างได้)
        if key == "invert":
            settings[key] = value if value in ("bw", "color") else None
            continue
        if key == "face":
            settings[key] = (
                None
                if value in (None, False)
                else float(np.clip(float(value), 0.0, 1.0))
            )
            continue
        if value is None:
            continue
        if key in ("color_fix", "scratch", "colorize"):
            settings[key] = bool(value)
        elif key == "face":
            settings[key] = None if value is None else float(np.clip(float(value), 0.0, 1.0))
        elif key == "upscale":
            scale = int(value)
            settings[key] = scale if scale in (1, 2, 4) else 2
        elif key == "invert_gamma":
            settings[key] = float(np.clip(float(value), 0.4, 2.5))
        else:
            settings[key] = float(np.clip(float(value), 0.0, 1.0))
    settings["_source_bits"] = source_bits
    return settings


class Engine:
    def __init__(self, preset: str = "color_negative", overrides: dict | None = None,
                 gpu: gpu_mod.GPUInfo | None = None, source_bits: int = 8,
                 max_pixels: int = DEFAULT_MAX_PIXELS):
        self.preset = preset
        self.gpu = gpu or gpu_mod.detect()
        self.settings = resolve_settings(preset, overrides, source_bits)
        self.source_bits = source_bits
        self.max_pixels = max_pixels
        # ไฟล์ 8-bit ผ่าน gamma มาแล้ว จึงแปลงเป็น linear ก่อนกลับสี (16-bit ถือว่า linear อยู่แล้ว)
        self.linearize = bool(self.settings.get("invert")) and source_bits <= 8

    # ---------- meta ----------
    def meta(self) -> dict:
        return {
            "device": self.gpu.device,
            "gpu": self.gpu.name,
            "fp16": self.gpu.fp16,
            "tile_size": self.gpu.tile_size,
            "linearize_input": self.linearize,
            "source_bits": self.source_bits,
            "max_pixels": self.max_pixels,
        }

    # ---------- plan ----------
    def plan(self) -> list[tuple[str, str, Callable[[np.ndarray], tuple[np.ndarray, str]]]]:
        s = self.settings
        steps: list[tuple[str, str, Callable]] = []
        if s.get("invert"):
            steps.append(("invert", "กลับสีเนกาทีฟ", self._step_invert))
        if s.get("color_fix"):
            steps.append(("color_fix", "แก้สีซีด/เพี้ยน", self._step_color_fix))
        if s.get("scratch"):
            steps.append(("scratch", "ลบรอยขีดข่วนและฝุ่น", self._step_scratch))
        if float(s.get("denoise") or 0) > 0:
            steps.append(("denoise", "ลดนอยส์และเกรน", self._step_denoise))
        if s.get("colorize"):
            steps.append(("colorize", "ใส่สี", self._step_colorize))
        if int(s.get("upscale") or 1) > 1:
            steps.append(("upscale", "เพิ่มความละเอียด", self._step_upscale))
        if s.get("face") is not None:
            steps.append(("face", "ฟื้นฟูใบหน้า", self._step_face))
        steps.append(("final", "ปรับแต่งขั้นสุดท้าย", self._step_final))
        return steps

    # ---------- run ----------
    def run(self, img: np.ndarray, progress: ProgressFn = None) -> RunResult:
        start = time.perf_counter()
        current = np.clip(np.asarray(img, dtype=np.float32), 0.0, 1.0)
        stages: list[Stage] = []
        warnings: list[str] = []
        plan = self.plan()
        total = len(plan)

        for index, (key, label, func) in enumerate(plan):
            if progress:
                progress(index / max(total, 1), f"{label}…")
            t0 = time.perf_counter()
            try:
                current, note = func(current)
            except (ModelUnavailable, ImportError) as exc:
                # เก็บภาพจากขั้นก่อนหน้าไว้แล้วเดินต่อ
                note = f"ข้ามขั้นนี้: {exc}"
                warnings.append(f"{label}: {exc} (ใช้ผลจากขั้นก่อนหน้าแทน)")
            except Exception as exc:  # ไม่ให้ทั้งงานล้มเพราะขั้นเดียว
                note = f"ผิดพลาด: {exc}"
                warnings.append(f"{label}: {exc}")
            stages.append(
                Stage(key=key, label=label, image=np.clip(current, 0.0, 1.0),
                      seconds=round(time.perf_counter() - t0, 2), note=note)
            )

        if progress:
            progress(1.0, "เสร็จแล้ว")
        return RunResult(
            preset=self.preset,
            settings=dict(self.settings),
            meta=self.meta(),
            stages=stages,
            warnings=warnings,
            elapsed=round(time.perf_counter() - start, 2),
        )

    # ---------- steps ----------
    def _step_invert(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        mode = self.settings["invert"]
        gamma = float(self.settings.get("invert_gamma", 1.0))
        work = film_invert.srgb_to_linear(img) if self.linearize else img

        if mode == "bw":
            out = film_invert.invert_bw_negative(work)
            out = np.repeat(out[..., None], 3, axis=2)
            note = "กลับสีเนกาทีฟขาวดำ"
        else:
            out = film_invert.invert_color_negative(work, gamma=gamma)
            note = "กลับสีเนกาทีฟสี + ตัดสีส้มฐานฟิล์ม"
        if self.linearize:
            out = film_invert.linear_to_srgb(out)
            note += " (แปลง sRGB → linear ตอนกลับสี)"
        return np.clip(out, 0.0, 1.0), note

    def _step_color_fix(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        strength = float(self.settings.get("color_fix_strength", 0.5))
        mode = "faded_color" if self.preset == "faded_color" else "slide"
        out = color_fix.restore_faded(img, strength, mode)
        return out, f"gray-world + ยืดฮิสโตแกรม + CLAHE + เพิ่มความสดสี (แรง {strength:.2f})"

    def _step_scratch(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        out, mask, note = scratch.remove_scratches(
            img,
            sensitivity=float(self.settings.get("scratch_strength", 0.6)),
            strength=float(self.settings.get("scratch_strength", 0.6)),
            use_lama=True,
            device=self.gpu.device,
        )
        return out, note

    def _step_denoise(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        out, note = denoise.denoise(img, float(self.settings.get("denoise", 0.5)))
        return out, note

    def _step_colorize(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        if not is_grayscale(img):
            return img, "ภาพมีสีอยู่แล้ว — ข้ามขั้นใส่สี"
        out, note = colorize.colorize(
            img,
            strength=float(self.settings.get("colorize_strength", 0.8)),
            device=self.gpu.device,
        )
        return out, note

    def _step_upscale(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        scale = int(self.settings.get("upscale") or 1)
        h, w = img.shape[:2]
        capped = False
        while scale > 1 and w * h * scale * scale > self.max_pixels:
            scale //= 2
            capped = True
        if scale <= 1:
            return img, f"ภาพ {w}×{h} ใหญ่เกินขีดจำกัดอยู่แล้ว — ข้ามขั้นขยายภาพ"

        out, note = upscale.upscale(
            img, scale, tile=self.gpu.tile_size, half=self.gpu.fp16, device=self.gpu.device
        )
        if capped:
            note += " (ลดสเกลเพราะภาพใหญ่เกินขีดจำกัดหน่วยความจำ)"
        return out, note

    def _step_face(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        out, note = face.restore_faces(
            img, float(self.settings.get("face") or 0.7), device=self.gpu.device
        )
        return out, note

    def _step_final(self, img: np.ndarray) -> tuple[np.ndarray, str]:
        out = color_fix.final_touch(
            img,
            wb=float(self.settings.get("final_wb", 0.3)),
            contrast=float(self.settings.get("final_contrast", 0.15)),
            saturation=float(self.settings.get("final_saturation", 0.1)),
            grain=float(self.settings.get("final_grain", 0.02)),
        )
        return out, "white balance + contrast + เติมเกรนเล็กน้อย"


def run_pipeline(img: np.ndarray, preset: str = "color_negative",
                 overrides: dict | None = None, gpu: gpu_mod.GPUInfo | None = None,
                 source_bits: int = 8, progress: ProgressFn = None) -> RunResult:
    """ทางลัดสำหรับเรียกใช้ครั้งเดียวจบ (ใช้โดย UI และสคริปต์ทดสอบ)"""
    engine = Engine(preset, overrides, gpu=gpu, source_bits=source_bits)
    return engine.run(img, progress=progress)
