"""ลดนอยส์และเกรนแต่เก็บรายละเอียดไว้ (ขั้นที่ 5)

ลำดับ: SCUNet (โมเดล color_real ที่ฝึกมากับภาพจริง) → ถ้าโหลดไม่ได้หรือพัง
ให้ใช้ Non-local Means ของ OpenCV แล้วเติมรายละเอียดความถี่สูงกลับบางส่วน
เพื่อไม่ให้ภาพดูพลาสติก

- `strength` 0 = ปิด, 1 = ใช้ผลจากโมเดลเต็มที่ (ผสมกับภาพต้นฉบับตามค่านี้)
- ภาพใหญ่ถูกแบ่งเป็นชิ้น (tile) พร้อมขอบซ้อน เพื่อไม่ให้ RAM บน CPU ระเบิด
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

from ..core.model_manager import ModelUnavailable, get_manager

SCUNET_KEY = "scunet_color_real_psnr"
SCUNET_TILE = 512
SCUNET_OVERLAP = 32

_lock = threading.RLock()
_scunet: dict[str, object] = {}


# ---------- SCUNet ----------
def _load_scunet(weights):
    try:
        import torch  # noqa: F401
        from .vendor import SCUNet
    except ImportError as exc:
        raise ModelUnavailable(
            "SCUNet ต้องติดตั้ง torch + einops (pip install torch einops)"
        ) from exc

    import torch

    net = SCUNet(in_nc=3, config=[4, 4, 4, 4, 4, 4, 4], dim=64)
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


get_manager().register(SCUNET_KEY, _load_scunet)


def _get_scunet(device: str):
    with _lock:
        net = _scunet.get(device)
        if net is None:
            net = get_manager().get(SCUNET_KEY).to(device).eval()
            _scunet[device] = net
        return net


def _to_tensor(img: np.ndarray):
    import torch

    arr = np.ascontiguousarray(np.clip(img, 0.0, 1.0).transpose(2, 0, 1))
    return torch.from_numpy(arr).float().unsqueeze(0)


def _from_tensor(tensor) -> np.ndarray:
    arr = tensor.detach().float().clamp(0.0, 1.0)[0].cpu().numpy()
    return np.transpose(arr, (1, 2, 0))


def _tile_starts(total: int, tile: int, step: int) -> list[int]:
    if total <= tile:
        return [0]
    starts = list(range(0, total - tile + 1, step))
    if starts[-1] + tile < total:
        starts.append(total - tile)
    return starts


def _blend_mask(height: int, width: int, ramp: int,
                top: bool, left: bool, bottom: bool, right: bool) -> np.ndarray:
    """น้ำหนักสำหรับผสานชิ้นภาพ: ลดหลั่นที่ขอบด้านในเพื่อให้รอยต่อเนียน"""
    mask = np.ones((height, width), dtype=np.float32)
    if ramp <= 0:
        return mask
    fade = np.linspace(0.02, 1.0, ramp, dtype=np.float32)
    if top:
        mask[:ramp, :] *= fade[:, None]
    if bottom:
        mask[-ramp:, :] *= fade[::-1][:, None]
    if left:
        mask[:, :ramp] *= fade[None, :]
    if right:
        mask[:, -ramp:] *= fade[::-1][None, :]
    return mask


def _scunet_forward(net, tensor, tile: int = SCUNET_TILE, overlap: int = SCUNET_OVERLAP):
    import torch

    _, _, height, width = tensor.shape
    if height <= tile and width <= tile:
        with torch.no_grad():
            return net(tensor)

    step = tile - overlap
    out = torch.zeros_like(tensor)
    weight = torch.zeros((1, 1, height, width), dtype=tensor.dtype, device=tensor.device)
    for top in _tile_starts(height, tile, step):
        for left in _tile_starts(width, tile, step):
            patch = tensor[:, :, top:top + tile, left:left + tile]
            ph, pw = patch.shape[2], patch.shape[3]
            with torch.no_grad():
                result = net(patch)[..., :ph, :pw]
            mask = _blend_mask(
                ph, pw, min(overlap, ph // 2, pw // 2),
                top > 0, left > 0,
                top + ph < height, left + pw < width,
            )
            mask_t = torch.from_numpy(mask)[None, None].to(result.device)
            out[:, :, top:top + ph, left:left + pw] += result * mask_t
            weight[:, :, top:top + ph, left:left + pw] += mask_t
    return out / weight.clamp_min(1e-4)


def _scunet_denoise(img: np.ndarray, strength: float, device: str):
    net = _get_scunet(device)
    tensor = _to_tensor(img).to(device)
    result = _from_tensor(_scunet_forward(net, tensor))
    blended = img * (1.0 - strength) + result * strength
    return np.clip(blended, 0.0, 1.0)


# ---------- NLM (สำรอง) ----------
def _to_u8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def _nlm_denoise(img: np.ndarray, strength: float) -> tuple[np.ndarray, str]:
    h = int(round(2 + 10 * strength))
    bgr = _to_u8(img)[..., ::-1]
    smoothed = cv2.fastNlMeansDenoisingColored(bgr, None, h, h, 7, 21)
    return smoothed[..., ::-1].astype(np.float32) / 255.0, f"NLM h={h}"


def denoise(img: np.ndarray, strength: float = 0.5, preserve_detail: float = 0.35,
            device: str = "cpu") -> tuple[np.ndarray, str]:
    """strength 0–1: 0 = ปิด, 1 = ลดแรงสุด"""
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength <= 0:
        return img, "ข้ามขั้นลดเกรน"

    try:
        out = _scunet_denoise(img, strength, device)
        note = f"SCUNet color-real (ผสม {strength:.2f})"
    except (ModelUnavailable, ImportError) as exc:
        out, note = _nlm_denoise(img, strength)
        note += f" — SCUNet ไม่พร้อม: {exc}"
    except Exception as exc:  # โมเดลพัง/หน่วยความจำไม่พอ ก็ยังลดเกรนต่อได้
        out, note = _nlm_denoise(img, strength)
        note += f" — SCUNet ใช้ไม่ได้ ({exc})"

    if preserve_detail > 0:
        low = cv2.GaussianBlur(img, (0, 0), 1.2)
        high = img - low
        out = np.clip(out + high * preserve_detail, 0.0, 1.0)
        note += f", เก็บรายละเอียด {int(preserve_detail * 100)}%"

    h_px, w_px = img.shape[:2]
    if h_px * w_px > 4_000_000 and "SCUNet" in note:
        note += " — ภาพใหญ่ใช้เวลาหลายสิบนาทีบน CPU"
    return out, note
