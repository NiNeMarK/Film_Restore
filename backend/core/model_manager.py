"""ดาวน์โหลด weights ครั้งแรก + lazy load (ตามแผนข้อ 6)

- weights เก็บใน backend/models (ไม่เข้า git)
- ถ้าวางไฟล์ชื่อเดียวกับใน `MODEL_SPECS` ไว้ในโฟลเดอร์นั้นแล้ว จะใช้ไฟล์ในเครื่องโดยไม่ดาวน์โหลด
- เปลี่ยนโฟลเดอร์ได้ด้วย env `FILM_RESTORE_MODELS`
"""

from __future__ import annotations

import os
import shutil
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

DEFAULT_MODELS_DIR = Path(
    os.environ.get("FILM_RESTORE_MODELS")
    or (Path(__file__).resolve().parents[1] / "models")
)

ProgressFn = Optional[Callable[[str, int, int], None]]


class ModelUnavailable(RuntimeError):
    """โมเดลหรือไลบรารีที่ต้องใช้ยังไม่พร้อม"""


@dataclass(frozen=True)
class ModelSpec:
    key: str
    filename: str
    label: str
    url: str = ""
    license: str = ""
    note: str = ""
    approx_mb: int = 0


MODEL_SPECS: dict[str, ModelSpec] = {
    "realesrgan_x2plus": ModelSpec(
        key="realesrgan_x2plus",
        filename="RealESRGAN_x2plus.pth",
        label="Real-ESRGAN x2",
        url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        license="BSD-3-Clause",
        note="Upscale x2",
        approx_mb=64,
    ),
    "realesrgan_x4plus": ModelSpec(
        key="realesrgan_x4plus",
        filename="RealESRGAN_x4plus.pth",
        label="Real-ESRGAN x4",
        url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/RealESRGAN_x4plus.pth",
        license="BSD-3-Clause",
        note="Upscale x4",
        approx_mb=64,
    ),
    "gfpgan_v14": ModelSpec(
        key="gfpgan_v14",
        filename="GFPGANv1.4.pth",
        label="GFPGAN v1.4",
        url="https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
        license="Apache-2.0",
        note="ฟื้นฟูใบหน้า (มีตัวปรับ fidelity)",
        approx_mb=348,
    ),
}


class ModelManager:
    """โหลดโมเดลแบบ lazy และดาวน์โหลด weights เมื่อยังไม่มี"""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or DEFAULT_MODELS_DIR)
        self.root.mkdir(parents=True, exist_ok=True)
        self._loaders: dict[str, Callable[[Path], object]] = {}
        self._loaded: dict[str, object] = {}
        self._lock = threading.RLock()

    # ---------- registry ----------
    def register(self, key: str, loader: Callable[[Path], object]) -> None:
        """ลงทะเบียนฟังก์ชันสร้างโมเดล (เรียกตอน import โมดูล pipeline)"""
        self._loaders[key] = loader

    def spec(self, key: str) -> ModelSpec:
        if key not in MODEL_SPECS:
            raise KeyError(f"ไม่รู้จักโมเดล '{key}'")
        return MODEL_SPECS[key]

    # ---------- weights ----------
    def path(self, key: str) -> Path:
        return self.root / self.spec(key).filename

    def is_downloaded(self, key: str) -> bool:
        path = self.path(key)
        return path.exists() and path.stat().st_size > 0

    def download(self, key: str, progress: ProgressFn = None) -> Path:
        spec = self.spec(key)
        target = self.path(key)
        if self.is_downloaded(key):
            return target
        if not spec.url:
            raise ModelUnavailable(f"{spec.label}: ไม่มี URL สำหรับดาวน์โหลด")

        tmp = target.with_suffix(target.suffix + ".part")
        request = urllib.request.Request(spec.url, headers={"User-Agent": "film-restore/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(tmp, "wb") as handle:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(key, done, total)
        shutil.move(str(tmp), str(target))
        return target

    # ---------- loading ----------
    def get(self, key: str, progress: ProgressFn = None) -> object:
        with self._lock:
            if key in self._loaded:
                return self._loaded[key]
            if key not in self._loaders:
                raise ModelUnavailable(
                    f"{key}: ยังไม่มีตัวโหลด — ติดตั้งไลบรารีที่เกี่ยวข้องก่อน"
                )
            weights = self.download(key, progress)
            obj = self._loaders[key](weights)
            self._loaded[key] = obj
            return obj

    def unload(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._loaded.clear()
            else:
                self._loaded.pop(key, None)

    def status(self) -> list[dict]:
        rows = []
        for key, spec in MODEL_SPECS.items():
            rows.append(
                {
                    "key": key,
                    "label": spec.label,
                    "license": spec.license,
                    "note": spec.note,
                    "approx_mb": spec.approx_mb,
                    "downloaded": self.is_downloaded(key),
                    "path": str(self.path(key)),
                }
            )
        return rows


_manager: ModelManager | None = None


def get_manager() -> ModelManager:
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
