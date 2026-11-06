"""FastAPI backend + เสิร์ฟหน้าเว็บ Gradio ที่ http://localhost:7860

API (ใช้ต่อยอดกับ React ในเฟส 3 ได้):
  GET  /api/health    สเปกเครื่อง + สถานะโมเดล
  GET  /api/presets   รายการโหมดและค่าเริ่มต้น
  POST /api/restore   อัปโหลดภาพ + ตั้งค่า แล้วคืนผลแต่ละขั้นพร้อม URL
  WS   /ws/restore    เหมือน POST แต่ส่งความคืบหน้าเป็น event ระหว่างรัน

รัน: python backend/main.py --host 127.0.0.1 --port 7860
เปิดให้มือถือในวง Wi-Fi เดียวกันใช้: python backend/main.py --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import uuid
import webbrowser
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.core import gpu as gpu_mod
from backend.core import paths
from backend.core.image_io import (
    IMAGE_EXTS,
    RAW_EXTS,
    crop_film_border,
    load_image,
    load_image_bytes,
    resize_max,
    save_image,
    to_jpeg_bytes,
)
from backend.core.model_manager import get_manager
from backend.pipeline.engine import Engine
from backend.pipeline.presets import PRESET_LABELS, PRESET_NOTES, PRESETS, get_preset

# โหมดซอร์ส = backend/outputs, โหมด .exe = %LOCALAPPDATA%\FilmRestore\outputs
OUTPUT_DIR = paths.outputs_dir()
# หน้าเว็บ React (เฟส 3) ที่ build แล้ว — ถ้ามีจะเสิร์ฟที่ /app
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend" / "dist"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
ALLOWED_EXTS = IMAGE_EXTS | RAW_EXTS

_gpu_cache: gpu_mod.GPUInfo | None = None


def gpu_info() -> gpu_mod.GPUInfo:
    global _gpu_cache
    if _gpu_cache is None:
        _gpu_cache = gpu_mod.detect()
    return _gpu_cache


def process_image(input_path: Path, preset: str, overrides: dict, crop: bool,
                  job_id: str, progress=None) -> dict:
    """รัน pipeline แล้วบันทึกผลทุกขั้นลง backend/outputs/<job_id>"""
    img, bits = load_image(input_path)
    source = crop_film_border(img) if crop else img

    engine = Engine(preset, overrides, gpu=gpu_info(), source_bits=bits)
    result = engine.run(source, progress=progress)

    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    save_image(job_dir / "original.png", source)

    stages = []
    for index, stage in enumerate(result.stages, start=1):
        filename = f"{index:02d}_{stage.key}.png"
        save_image(job_dir / filename, stage.image)
        payload = stage.as_dict()
        payload["url"] = f"/files/{job_id}/{filename}"
        stages.append(payload)

    save_image(job_dir / "result.png", result.image)

    meta = result.as_dict()
    meta.update(
        {
            "job": job_id,
            "original": {"width": source.shape[1], "height": source.shape[0], "bits": bits},
            "original_url": f"/files/{job_id}/original.png",
            "result_url": f"/files/{job_id}/result.png",
            "stages": stages,
        }
    )
    (job_dir / "settings.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


async def _send(websocket: WebSocket, payload: dict) -> bool:
    """ส่ง JSON กลับ — คืน False ถ้า client ปิดไปแล้ว"""
    try:
        await websocket.send_json(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False


async def _run_ws_job(websocket: WebSocket, settings: dict, data: bytes) -> None:
    """รันงานเดียวจาก WebSocket แล้วสตรีม progress กลับจนจบ

    event ที่ส่งกลับ: {"type": "progress"|"stage"|"done"|"error", ...}
    """
    preset = settings.get("preset", "color_negative")
    if preset not in PRESETS:
        await _send(websocket, {"type": "error", "detail": f"ไม่รู้จักโหมด '{preset}'"})
        return

    overrides = settings.get("overrides") or {}
    if not isinstance(overrides, dict):
        await _send(websocket, {"type": "error", "detail": "overrides ต้องเป็น JSON object"})
        return

    suffix = Path(str(settings.get("filename") or "upload.png")).suffix.lower() or ".png"
    if suffix not in ALLOWED_EXTS:
        await _send(
            websocket,
            {
                "type": "error",
                "detail": f"ไม่รองรับไฟล์ '{suffix}' (รองรับ: {', '.join(sorted(ALLOWED_EXTS))})",
            },
        )
        return
    if not data:
        await _send(websocket, {"type": "error", "detail": "ไม่ได้รับข้อมูลภาพ"})
        return

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:12]
    upload_path = UPLOAD_DIR / f"{job_id}{suffix}"
    upload_path.write_bytes(data)

    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()

    def progress(fraction: float, message: str) -> None:
        loop.call_soon_threadsafe(events.put_nowait, ("progress", fraction, message))

    def job() -> None:
        try:
            payload = process_image(
                upload_path,
                preset,
                overrides,
                bool(settings.get("crop_border", True)),
                job_id,
                progress=progress,
            )
        except Exception as exc:  # แจ้ง client แล้วรอรับงานถัดไป
            loop.call_soon_threadsafe(events.put_nowait, ("error", 0.0, str(exc)))
        else:
            loop.call_soon_threadsafe(events.put_nowait, ("done", 1.0, payload))

    loop.run_in_executor(None, job)

    while True:
        kind, fraction, payload = await events.get()
        if kind == "progress":
            ok = await _send(
                websocket,
                {"type": "progress", "progress": round(float(fraction), 3), "message": payload},
            )
        elif kind == "error":
            ok = await _send(websocket, {"type": "error", "detail": payload})
        else:
            ok = await _send(websocket, {"type": "done", **payload})
        if not ok or kind != "progress":
            return


def create_app(with_ui: bool = True) -> FastAPI:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Film Restore", version="0.1.0")
    app.mount("/files", StaticFiles(directory=str(OUTPUT_DIR)), name="files")

    # มีหน้า React ที่ build ไว้แล้วหรือไม่ — ถ้ามีจะให้เป็นหน้าหลักที่ "/" และย้าย Gradio ไป "/classic"
    react_ready = (FRONTEND_DIR / "index.html").is_file()

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "gpu": gpu_info().as_dict(),
            "models": get_manager().status(),
        }

    @app.get("/api/presets")
    def list_presets():
        return {
            "labels": PRESET_LABELS,
            "notes": PRESET_NOTES,
            "defaults": {key: get_preset(key) for key in PRESETS},
        }

    @app.post("/api/restore")
    async def restore(
        file: UploadFile = File(...),
        preset: str = Form("color_negative"),
        overrides: str = Form("{}"),
        crop_border: bool = Form(True),
    ):
        if preset not in PRESETS:
            raise HTTPException(status_code=400, detail=f"ไม่รู้จักโหมด '{preset}'")

        try:
            parsed = json.loads(overrides or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"overrides ต้องเป็น JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="overrides ต้องเป็น JSON object")

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"ไม่รองรับไฟล์ '{suffix or 'ไม่ทราบนามสกุล'}' "
                f"(รองรับ: {', '.join(sorted(ALLOWED_EXTS))})",
            )

        job_id = uuid.uuid4().hex[:12]
        upload_path = UPLOAD_DIR / f"{job_id}{suffix}"
        upload_path.write_bytes(await file.read())

        try:
            payload = await run_in_threadpool(
                process_image, upload_path, preset, parsed, bool(crop_border), job_id
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return JSONResponse(payload)

    @app.post("/api/preview")
    async def preview(
        file: UploadFile = File(...),
        preset: str = Form("color_negative"),
        overrides: str = Form("{}"),
        crop_border: bool = Form(True),
        max_side: int = Form(420),
    ):
        """พรีวิวเร็ว ๆ บนภาพย่อสำหรับสไลเดอร์ — ทำเฉพาะขั้นเบา ไม่โหลดโมเดล AI"""
        if preset not in PRESETS:
            raise HTTPException(status_code=400, detail=f"ไม่รู้จักโหมด '{preset}'")

        try:
            parsed = json.loads(overrides or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"overrides ต้องเป็น JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="overrides ต้องเป็น JSON object")

        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="ไม่ได้รับข้อมูลภาพ")

        def work() -> bytes:
            img, _bits = load_image_bytes(data)
            if crop_border:
                img = crop_film_border(img)
            img, _scale = resize_max(img, int(max(160, min(1024, max_side))))
            # ข้ามขั้นที่ต้องใช้โมเดล/ช้า เพื่อให้ตอบกลับเร็วระดับลากสไลเดอร์
            fast = {
                **parsed,
                "scratch": False,
                "denoise": 0.0,
                "colorize": False,
                "upscale": 1,
                "face": None,
            }
            result = Engine(preset, fast, gpu=gpu_info()).run(img)
            return to_jpeg_bytes(result.image, quality=84)

        try:
            jpeg = await run_in_threadpool(work)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.websocket("/ws/restore")
    async def ws_restore(websocket: WebSocket):
        """client ส่ง text JSON (settings) ตามด้วย binary ภาพ — รับได้หลายงานต่อ connection

        ตัวอย่าง:
          ws.send({"preset": "color_negative", "overrides": {"face": null}})
          ws.send(image_bytes)
          -> {"type": "progress", "progress": 0.2, "message": "กลับสีเนกาทีฟ…"}
          -> {"type": "done", ...ผลเหมือน POST /api/restore}
        """
        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    settings = json.loads(raw or "{}")
                except json.JSONDecodeError as exc:
                    await _send(
                        websocket, {"type": "error", "detail": f"settings ต้องเป็น JSON: {exc}"}
                    )
                    continue
                if not isinstance(settings, dict):
                    await _send(websocket, {"type": "error", "detail": "settings ต้องเป็น JSON object"})
                    continue

                data = await websocket.receive_bytes()
                await _run_ws_job(websocket, settings, data)
        except WebSocketDisconnect:
            return

    @app.get("/classic", include_in_schema=False)
    def classic_redirect():
        """/classic -> /classic/ (ไม่งั้นจะได้ 404 เพราะเป็น mount)"""
        return RedirectResponse(url="/classic/")

    if with_ui:
        try:
            import gradio as gr

            from backend.ui import CSS as UI_CSS
            from backend.ui import build_ui, theme as ui_theme
        except ImportError as exc:  # pragma: no cover - ขึ้นกับการติดตั้ง
            raise RuntimeError(
                "ต้องติดตั้ง gradio เพื่อใช้หน้าเว็บ (pip install gradio) "
                "หรือรันด้วย FILM_RESTORE_API_ONLY=1 เพื่อใช้เฉพาะ API"
            ) from exc

        app = gr.mount_gradio_app(
            app,
            build_ui(gpu_info()),
            path="/classic" if react_ready else "/",
            theme=ui_theme(),
            css=UI_CSS,
        )

    # React เป็นหน้าหลัก — mount ท้ายสุดเพื่อไม่ให้กลืน /api, /files, /ws และ /classic
    if react_ready:
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="film-restore-app",
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Film Restore — localhost web app")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 เพื่อให้เครื่องอื่นในวงเดียวกันเข้าได้")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true", help="ไม่ต้องเปิดเบราว์เซอร์อัตโนมัติ")
    parser.add_argument("--cpu", action="store_true", help="บังคับใช้ CPU")
    parser.add_argument("--api-only", action="store_true", help="ไม่ต้องเสิร์ฟหน้า Gradio")
    args = parser.parse_args()

    if args.cpu:
        os.environ["FILM_RESTORE_CPU"] = "1"

    app = create_app(with_ui=not args.api_only)
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}"
    print(f"Film Restore: {url}")
    info = gpu_info()
    print(f"Device: {info.device} ({info.name}) | tile={info.tile_size} | fp16={info.fp16}")

    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
