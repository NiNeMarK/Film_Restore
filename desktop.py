"""โหมดเดสก์ท็อป — ใช้ UI ชุดเดียวกับเว็บ แต่เปิดในหน้าต่างโปรแกรม (pywebview)

รัน: python desktop.py
แพ็กเป็น .exe: pyinstaller --noconfirm --windowed --name FilmRestore desktop.py
(ต้องติดตั้ง pywebview และ pyinstaller ก่อน — ดู requirements.txt)
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn

from backend.main import create_app

HOST = "127.0.0.1"
PORT = 7860


def _wait_for_port(host: str, port: int, timeout: float = 120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.2)
    return False


def main() -> None:
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "โหมดเดสก์ท็อปต้องติดตั้ง pywebview (pip install pywebview) "
            "หรือใช้โหมดเว็บ: python backend/main.py"
        ) from exc

    config = uvicorn.Config(create_app(), host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    if not _wait_for_port(HOST, PORT):
        raise SystemExit("เซิร์ฟเวอร์ภายในไม่ตอบสนอง — ลองรัน python backend/main.py เพื่อดูข้อผิดพลาด")

    webview.create_window("Film Restore", f"http://{HOST}:{PORT}", width=1320, height=900)
    webview.start()
    server.should_exit = True


if __name__ == "__main__":
    main()
