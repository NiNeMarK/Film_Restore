"""โฟลเดอร์เก็บข้อมูลที่โปรแกรมเขียนได้ (weights, ผลลัพธ์, log)

รันจากซอร์สใช้โฟลเดอร์เดิมในโปรเจกต์ (`backend/models`, `backend/outputs`)
แต่ .exe ที่แพ็กด้วย PyInstaller ต้องเขียนลงโฟลเดอร์ผู้ใช้ เพราะโฟลเดอร์โปรแกรม
อาจอยู่ใต้ Program Files (เขียนไม่ได้) หรือเป็น temp ที่ถูกลบเมื่อปิดโปรแกรม

ลำดับการเลือก:
1. env `FILM_RESTORE_DATA` — กำหนดโฟลเดอร์ข้อมูลทั้งก้อนเอง
2. env `FILM_RESTORE_MODELS` — กำหนดเฉพาะโฟลเดอร์ weights
3. โหมด .exe (`sys.frozen`) — `%LOCALAPPDATA%\\FilmRestore`
4. โหมดซอร์ส — โฟลเดอร์โปรเจกต์
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "FilmRestore"

# backend/core/paths.py -> โฟลเดอร์โปรเจกต์
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def is_frozen() -> bool:
    """โปรแกรมถูกรันจากไฟล์ .exe ที่แพ็กแล้วหรือไม่"""
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    """โฟลเดอร์หลักสำหรับข้อมูลที่เขียนได้"""
    override = os.environ.get("FILM_RESTORE_DATA")
    if override:
        base = Path(override).expanduser()
    elif is_frozen():
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = (
            Path(local) / APP_NAME
            if local
            else Path.home() / f".{APP_NAME.lower()}"
        )
    else:
        base = PROJECT_ROOT

    base.mkdir(parents=True, exist_ok=True)
    return base


def models_dir() -> Path:
    """ที่เก็บ weights ของโมเดล (โหลดครั้งแรกแล้วใช้ซ้ำ)"""
    override = os.environ.get("FILM_RESTORE_MODELS")
    if override:
        path = Path(override).expanduser()
    elif is_frozen():
        path = data_dir() / "models"
    else:
        path = PROJECT_ROOT / "backend" / "models"

    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_dir() -> Path:
    """ที่เก็บผลลัพธ์ของแต่ละงาน (ภาพทุกขั้น + settings.json)"""
    path = data_dir() / ("outputs" if is_frozen() else "backend/outputs")
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    """ไฟล์ log ของโหมดเดสก์ท็อป (ใช้เมื่อไม่มีหน้าต่าง console)"""
    return data_dir() / "film-restore.log"
