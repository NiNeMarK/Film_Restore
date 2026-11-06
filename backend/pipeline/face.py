"""ฟื้นฟูใบหน้าด้วย CodeFormer (หลัก) → GFPGAN (สำรอง) — ขั้นที่ 8

- CodeFormer: ปรับ fidelity ผ่าน `w` (0 = สวย/เน้นคุณภาพ, 1 = เหมือนต้นฉบับ)
- ภาพทั้งภาพถูกตรวจใบหน้าด้วย RetinaFace (facexlib) แล้ววางใบหน้าที่ฟื้นฟูกลับ
- ถ้า torch/facexlib/weights ยังไม่พร้อม จะลอง GFPGAN ต่อ และถ้าไม่มีทั้งคู่
  จะโยน `ModelUnavailable` ให้ engine ข้ามขั้นนี้พร้อมคำเตือน (ไม่ทำทั้งงานล้ม)

อาร์คิเทกเจอร์ของ CodeFormer อยู่ใน `vendor/` (ดูเหตุผลใน `vendor/__init__.py`)
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from ..core.model_manager import ModelUnavailable, get_manager

CODEFORMER_KEY = "codeformer"
GFPGAN_KEY = "gfpgan_v14"

_lock = threading.RLock()
_codeformer: dict[tuple[str, str], dict] = {}
_gfpgan: dict[str, object] = {}


def _to_bgr_u8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)[..., ::-1]


def _bgr_to_tensor(face_bgr: np.ndarray):
    """BGR uint8 -> tensor [1,3,H,W] ช่วง [-1,1] (RGB) ตามที่ CodeFormer ต้องการ"""
    import torch

    rgb = np.ascontiguousarray(face_bgr[:, :, ::-1].astype(np.float32) / 255.0)
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
    return (tensor - 0.5) / 0.5


def _tensor_to_bgr(output) -> np.ndarray:
    arr = output.detach().float().clamp(-1.0, 1.0)[0].cpu().numpy()
    arr = np.transpose(arr, (1, 2, 0))          # RGB ใน [-1,1]
    arr = (arr + 1.0) / 2.0                     # RGB ใน [0,1]
    arr = np.clip(arr, 0.0, 1.0)[..., ::-1]     # -> BGR
    return (arr * 255.0).round().astype(np.uint8)


# ---------- CodeFormer ----------
def _load_codeformer(weights):
    try:
        import torch
        from .vendor import CodeFormer
    except ImportError as exc:
        raise ModelUnavailable(
            "CodeFormer ต้องติดตั้ง torch + einops (pip install torch einops)"
        ) from exc

    net = CodeFormer(
        dim_embd=512,
        codebook_size=1024,
        n_head=8,
        n_layers=9,
        connect_list=["32", "64", "128", "256"],
    )
    checkpoint = torch.load(str(weights), map_location="cpu", weights_only=True)
    if isinstance(checkpoint, dict):
        for name in ("params_ema", "params", "state_dict"):
            if name in checkpoint:
                checkpoint = checkpoint[name]
                break
    net.load_state_dict(checkpoint, strict=True)
    net.eval()
    for param in net.parameters():
        param.requires_grad_(False)
    return net


get_manager().register(CODEFORMER_KEY, _load_codeformer)


def _get_codeformer(device: str) -> dict:
    try:
        from facexlib.utils.face_restoration_helper import FaceRestoreHelper
    except ImportError as exc:
        raise ModelUnavailable(
            "ฟื้นฟูใบหน้าด้วย CodeFormer ต้องติดตั้ง facexlib (pip install facexlib)"
        ) from exc

    key = (CODEFORMER_KEY, device)
    with _lock:
        runtime = _codeformer.get(key)
        if runtime is None:
            net = get_manager().get(CODEFORMER_KEY).to(device).eval()
            helper = FaceRestoreHelper(
                upscale_factor=1,
                face_size=512,
                crop_ratio=(1, 1),
                det_model="retinaface_resnet50",
                save_ext="png",
                use_parse=True,
                device=device,
            )
            runtime = {"net": net, "helper": helper}
            _codeformer[key] = runtime
        return runtime


def _restore_with_codeformer(img: np.ndarray, fidelity: float, device: str):
    import torch

    runtime = _get_codeformer(device)
    net, helper = runtime["net"], runtime["helper"]
    bgr = _to_bgr_u8(img)

    with _lock:  # helper เก็บสถานะระหว่าง detect → paste จึงใช้ได้ทีละงาน
        helper.clean_all()
        try:
            helper.read_image(bgr)
            count = helper.get_face_landmarks_5(
                only_center_face=False, resize=640, eye_dist_threshold=5
            )
            if count == 0:
                return img, "ไม่พบใบหน้าในภาพ — ข้ามขั้นฟื้นฟูใบหน้า"

            helper.align_warp_face()
            for cropped in helper.cropped_faces:
                with torch.no_grad():
                    output = net(_bgr_to_tensor(cropped).to(device), w=fidelity, adain=True)[0]
                helper.add_restored_face(_tensor_to_bgr(output))

            helper.get_inverse_affine(None)
            restored = helper.paste_faces_to_input_image(upsample_img=None)
        finally:
            helper.clean_all()

    if restored is None:
        return img, "ไม่พบใบหน้าในภาพ — ข้ามขั้นฟื้นฟูใบหน้า"
    if restored.shape[:2] != img.shape[:2]:
        restored = cv2.resize(restored, (img.shape[1], img.shape[0]),
                              interpolation=cv2.INTER_LANCZOS4)
    out = restored[..., ::-1].astype(np.float32) / 255.0
    return np.clip(out, 0.0, 1.0), f"CodeFormer (fidelity {fidelity:.2f}, {count} หน้า)"


# ---------- GFPGAN (สำรอง) ----------
def _load_gfpgan(weights):
    try:
        from gfpgan import GFPGANer  # noqa: F401
    except ImportError as exc:
        raise ModelUnavailable(
            "ฟื้นฟูใบหน้าด้วย GFPGAN ต้องติดตั้ง gfpgan (pip install gfpgan)"
        ) from exc
    return weights


get_manager().register(GFPGAN_KEY, _load_gfpgan)


def _get_gfpgan(device: str):
    try:
        from gfpgan import GFPGANer
    except ImportError as exc:
        raise ModelUnavailable(
            "ฟื้นฟูใบหน้าด้วย GFPGAN ต้องติดตั้ง gfpgan (pip install gfpgan)"
        ) from exc

    with _lock:
        restorer = _gfpgan.get(device)
        if restorer is None:
            restorer = GFPGANer(
                model_path=str(get_manager().get(GFPGAN_KEY)),
                upscale=1,
                arch="clean",
                channel_multiplier=2,
                bg_upsampler=None,
                device=device,
            )
            _gfpgan[device] = restorer
        return restorer


def _restore_with_gfpgan(img: np.ndarray, fidelity: float, device: str):
    restorer = _get_gfpgan(device)
    bgr = _to_bgr_u8(img)
    _, _, restored = restorer.enhance(
        bgr,
        has_aligned=False,
        only_center_face=False,
        paste_back=True,
        weight=fidelity,
    )
    if restored is None:
        return img, "ไม่พบใบหน้าในภาพ — ข้ามขั้นฟื้นฟูใบหน้า"
    if restored.shape[:2] != img.shape[:2]:
        restored = cv2.resize(restored, (img.shape[1], img.shape[0]),
                              interpolation=cv2.INTER_LANCZOS4)
    out = restored[..., ::-1].astype(np.float32) / 255.0
    return np.clip(out, 0.0, 1.0), f"GFPGAN v1.4 (fidelity {fidelity:.2f})"


# ---------- ทางเข้าเดียว ----------
def restore_faces(img: np.ndarray, fidelity: float = 0.7, device: str = "cpu"):
    """คืน (ภาพ, หมายเหตุ) — ถ้าไม่พบใบหน้าจะคืนภาพเดิม"""
    fidelity = float(np.clip(fidelity, 0.0, 1.0))

    try:
        return _restore_with_codeformer(img, fidelity, device)
    except (ModelUnavailable, ImportError) as exc:
        reason = str(exc)
    except Exception as exc:  # CodeFormer พังก็ยังลอง GFPGAN ต่อ
        reason = f"CodeFormer ใช้ไม่ได้ ({exc})"

    try:
        out, note = _restore_with_gfpgan(img, fidelity, device)
    except (ModelUnavailable, ImportError) as exc:
        raise ModelUnavailable(f"{reason}; {exc}") from exc
    return out, f"{note} — {reason}"
