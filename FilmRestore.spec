# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — แพ็ก Film Restore เป็นโฟลเดอร์โปรแกรม (onedir)

    pyinstaller --noconfirm FilmRestore.spec
    ผลลัพธ์: dist/FilmRestore/FilmRestore.exe

ทำไม onedir ไม่ใช่ onefile: torch + CUDA มีขนาดหลาย GB ถ้าเป็น onefile
ทุกครั้งที่เปิดโปรแกรมจะต้องแตกไฟล์ลง temp ใหม่ (ช้า กินดิสก์ และเปิดซ้ำไม่ได้ถ้า temp เต็ม)
onedir เปิดได้ทันทีและวางไฟล์ข้าง .exe ได้เลย

weights ของโมเดลไม่ถูกฝังใน .exe — ดาวน์โหลดครั้งแรกตอนใช้งาน แล้วเก็บที่
%LOCALAPPDATA%\\FilmRestore\\models (ดู backend/core/paths.py)
"""

import glob
import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
    get_package_paths,
)

datas = []
# templates/ = หน้าเว็บที่ Gradio เสิร์ฟ (ขาดไม่ได้ ไม่งั้นเห็นหน้าเปล่า)
# include_py_files = Gradio อ่านไฟล์ .py ของตัวเองตอน import เพื่อสร้าง .pyi ให้ autocomplete
datas += collect_data_files("gradio", include_py_files=True)
datas += collect_data_files("webview", subdir="lib")
datas += collect_data_files("pythonnet")  # Python.Runtime.dll สำหรับ pywebview/.NET
datas += collect_data_files("clr_loader")
datas += collect_data_files("facexlib")  # config ของ RetinaFace (ตรวจใบหน้า)
# แพ็กเกจที่อ่าน version.txt ของตัวเองตอน import
datas += collect_data_files("safehttpx")
datas += collect_data_files("groovy")
# เก็บ metadata ไว้ให้ importlib.metadata.version() ใช้ได้ (gradio เช็คเวอร์ชันตัวเอง)
datas += copy_metadata("gradio")
datas += copy_metadata("gradio_client")
# โค้ดของเราเอง: ต้องมีไฟล์ .py อยู่จริงเพราะ vqgan_arch.py ใช้ @torch.jit.script
# ซึ่งอ่าน source ของฟังก์ชันตอนรัน (ถ้าไม่มีไฟล์จะได้ "Can't get source for <function swish>")
for _source in glob.glob(os.path.join(SPECPATH, "backend", "**", "*.py"), recursive=True):
    datas.append((_source, os.path.relpath(os.path.dirname(_source), SPECPATH)))

# torchvision 0.29 เปลี่ยนชื่อ native module เป็น _C_stable / image_stable
# ซึ่ง hook มาตรฐานหาไม่เจอ (.pyd และ dll ของ torchvision จึงหายไปทั้งชุด)
binaries = []
_tv_root, _tv_pkg = get_package_paths("torchvision")
for pattern in ("*.pyd", "*.dll"):
    for found in glob.glob(os.path.join(_tv_pkg, pattern)):
        binaries.append((found, "torchvision"))

# import ที่ตัววิเคราะห์มองไม่เห็น: import ในฟังก์ชัน, ผ่าน __getattr__, หรือเลือกตอนรัน
hiddenimports = [
    "backend.pipeline.vendor._compat",
    "backend.pipeline.vendor.codeformer_arch",
    "backend.pipeline.vendor.vqgan_arch",
    "backend.pipeline.vendor.scunet_arch",
    "multipart",  # python-multipart สำหรับอัปโหลดไฟล์ใน FastAPI
    "webview.platforms.winforms",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]
hiddenimports += collect_submodules("gradio")

# ไม่ฝังของที่ใช้กับ torchvision รุ่นนี้ไม่ได้ (import พังตั้งแต่ต้นทาง) หรือไม่ได้ติดตั้ง
# pipeline ถอยไปใช้ทางสำรองเอง: upscale -> Lanczos, ใส่สี -> ข้ามขั้น, ลบรอย -> OpenCV
excludes = [
    "basicsr",
    "realesrgan",
    "gfpgan",
    "modelscope",
    "simple_lama_inpainting",
    "pytest",
    "IPython",
    "jupyter",
]

a = Analysis(
    ["desktop.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FilmRestore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FilmRestore",
)
