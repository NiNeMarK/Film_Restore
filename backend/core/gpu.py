"""ตรวจสเปกเครื่อง (GPU/VRAM) แล้วปรับ fp16, ขนาด tile และฟีเจอร์ให้อัตโนมัติ

ใช้ตามแผนข้อ 5: "โปรแกรมตรวจ VRAM ตอนเปิด แล้วปรับขนาด tile และเปิดหรือปิดฟีเจอร์ให้อัตโนมัติ"
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field

# (VRAM สูงสุดของระดับ, ขนาด tile)
_TILE_TABLE = ((6.0, 256), (10.0, 384), (float("inf"), 512))


@dataclass
class GPUInfo:
    backend: str = "cpu"          # cuda | mps | cpu
    device: str = "cpu"           # cuda:0 | mps | cpu
    name: str = "CPU"
    total_vram_gb: float = 0.0
    free_vram_gb: float = 0.0
    fp16: bool = False
    tile_size: int = 0            # 0 = ไม่ต้องแบ่ง tile
    can_diffusion: bool = False
    torch_available: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def is_gpu(self) -> bool:
        return self.backend in ("cuda", "mps")


def _tile_for(vram_gb: float) -> int:
    for limit, tile in _TILE_TABLE:
        if vram_gb <= limit:
            return tile
    return 512


def detect(force_cpu: bool = False) -> GPUInfo:
    """ตรวจเครื่องครั้งเดียวตอนเปิดโปรแกรม"""
    if force_cpu or os.environ.get("FILM_RESTORE_CPU") == "1":
        return GPUInfo(notes=["เปิดโหมด CPU ตามที่กำหนด"])

    try:
        import torch
    except ImportError:
        return GPUInfo(
            notes=[
                "ไม่พบ PyTorch — จะใช้ CPU และวิธีประมวลผลแบบดั้งเดิม "
                "(ติดตั้ง torch เพื่อใช้โมเดล AI)"
            ]
        )

    notes: list[str] = []
    try:
        if torch.cuda.is_available():
            index = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(index)
            total = props.total_memory / 1024**3
            free, _ = torch.cuda.mem_get_info(index)
            free_gb = free / 1024**3
            info = GPUInfo(
                backend="cuda",
                device=f"cuda:{index}",
                name=props.name,
                total_vram_gb=round(total, 1),
                free_vram_gb=round(free_gb, 1),
                fp16=total >= 4.0 or props.major >= 6,
                tile_size=_tile_for(total),
                can_diffusion=total >= 16.0,
                torch_available=True,
            )
            if info.tile_size:
                notes.append(f"VRAM {total:.1f} GB — ใช้ fp16 และแบ่ง tile {info.tile_size} px")
            if not info.can_diffusion:
                notes.append("VRAM ไม่ถึง 16 GB — ปิดโหมด Diffusion ไว้")
            info.notes = notes
            return info

        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return GPUInfo(
                backend="mps",
                device="mps",
                name="Apple Silicon (MPS)",
                fp16=True,
                tile_size=384,
                torch_available=True,
                notes=["ใช้ MPS ของ Apple — บางโมเดลอาจไม่รองรับ"],
            )
    except Exception as exc:  # pragma: no cover - ขึ้นกับไดรเวอร์ของเครื่อง
        notes.append(f"ตรวจ GPU ไม่สำเร็จ: {exc}")

    return GPUInfo(torch_available=True, notes=notes + ["ไม่พบ GPU ที่ใช้ได้ — ใช้ CPU"])


def torch_dtype(info: GPUInfo):
    """คืน dtype ของ torch ตามผลตรวจ (คืน None ถ้าไม่มี torch)"""
    if not info.fp16:
        return None
    try:
        import torch

        return torch.float16
    except ImportError:
        return None
