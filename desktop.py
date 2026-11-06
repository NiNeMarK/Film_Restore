"""โหมดเดสก์ท็อป — ใช้ UI ชุดเดียวกับเว็บ แต่เปิดในหน้าต่างโปรแกรม (pywebview)

รันจากซอร์ส:  python desktop.py
แพ็กเป็น .exe: pyinstaller --noconfirm FilmRestore.spec  ->  dist/FilmRestore/FilmRestore.exe

ตอนรันจาก .exe จะไม่มีหน้าต่าง console (build แบบ windowed) ทำให้เห็น error ยาก
โปรแกรมจึงเขียน log ลง `%LOCALAPPDATA%\\FilmRestore\\film-restore.log` เสมอ
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from backend.core import paths
from backend.main import create_app

HOST = "127.0.0.1"
DEFAULT_PORT = 7860


def _free_port(preferred: int = DEFAULT_PORT) -> int:
    """ใช้พอร์ตเดิมถ้าว่าง ไม่งั้นหาพอร์ตว่างให้ (กันชนกับโหมดเว็บที่เปิดค้างอยู่)"""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((HOST, port))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise SystemExit("หาพอร์ตว่างสำหรับเซิร์ฟเวอร์ภายในไม่ได้")


def _wait_for_port(host: str, port: int, timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.2)
    return False


def _setup_logging() -> None:
    """โหมด .exe ไม่มี console — ส่ง stdout/stderr ลงไฟล์ในโฟลเดอร์ข้อมูลผู้ใช้"""
    if not paths.is_frozen():
        return
    try:
        handle = open(paths.log_path(), "a", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = handle
    sys.stderr = handle
    print(f"\n===== เปิดโปรแกรม {time.strftime('%Y-%m-%d %H:%M:%S')} =====", flush=True)


def _report_failure(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
    if not paths.is_frozen():
        return
    try:  # แจ้งผู้ใช้ด้วยกล่องข้อความของ Windows เพราะไม่มี console ให้ดู
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Film Restore", 0x10)
    except Exception:
        pass


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "โหมดเดสก์ท็อปต้องติดตั้ง pywebview (pip install pywebview) "
            "หรือใช้โหมดเว็บ: python backend/main.py"
        ) from exc

    port = _free_port()
    config = uvicorn.Config(create_app(), host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    if not _wait_for_port(HOST, port):
        raise SystemExit("เซิร์ฟเวอร์ภายในไม่ตอบสนอง — ลองรัน python backend/main.py เพื่อดูข้อผิดพลาด")

    print(f"Film Restore (เดสก์ท็อป): http://{HOST}:{port}", flush=True)
    print(f"ข้อมูลที่โปรแกรมเขียนได้: {paths.data_dir()}", flush=True)
    webview.create_window("Film Restore", f"http://{HOST}:{port}", width=1320, height=900)
    webview.start()
    server.should_exit = True


if __name__ == "__main__":
    _setup_logging()
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # เขียน log + กล่องข้อความ ก่อนปิดหน้าต่างไปเฉย ๆ
        _report_failure(
            "Film Restore เปิดไม่สำเร็จ:\n\n"
            + traceback.format_exc()[-1500:]
            + f"\n\nlog: {paths.log_path()}"
        )
        raise
