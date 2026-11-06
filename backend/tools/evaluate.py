"""วัดคุณภาพผลลัพธ์เทียบภาพอ้างอิง (แผนข้อ 9)

ชุดทดสอบตายตัว: โฟลเดอร์ `--input` (ภาพที่เสีย/ฟิล์ม) และ `--reference` (ต้นฉบับ)
จับคู่ด้วยชื่อไฟล์ (stem เดียวกัน นามสกุลต่างกันได้) แล้วรัน pipeline ตาม preset
จากนั้นรายงาน PSNR / SSIM / LPIPS / colorfulness ต่อภาพ พร้อมค่าเฉลี่ย

รัน:
  python backend/tools/evaluate.py \
      --input  testset/in \
      --reference testset/ref \
      --preset faded_color \
      --out backend/outputs/eval

  python backend/tools/evaluate.py ... --lpips     # เพิ่ม LPIPS (ต้อง pip install lpips)

ผลลัพธ์: metrics.csv (ต่อภาพ), summary.json (ค่าเฉลี่ย + ค่าที่ใช้), ภาพผลใน --out/result
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core import gpu as gpu_mod
from backend.core.image_io import IMAGE_EXTS, crop_film_border, load_image, save_image
from backend.pipeline.engine import Engine
from backend.pipeline.presets import PRESETS


# ---------- ตัวชี้วัด ----------
def to_gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img.astype(np.float32), cv2.COLOR_RGB2GRAY)


def psnr(a: np.ndarray, b: np.ndarray, peak: float = 1.0) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    if mse <= 0:
        return 100.0  # เหมือนกันทุกพิกเซล — กันค่า inf ในรายงาน
    return float(10.0 * np.log10(peak ** 2 / mse))


def ssim(a: np.ndarray, b: np.ndarray, sigma: float = 1.5, window: int = 11) -> float:
    """SSIM บนภาพระดับสีเทา ด้วย Gaussian window (แบบเดียวกับ Wang et al. 2004)"""
    x = to_gray(a).astype(np.float64)
    y = to_gray(b).astype(np.float64)
    c1 = (0.01 * 1.0) ** 2
    c2 = (0.03 * 1.0) ** 2

    mu_x = cv2.GaussianBlur(x, (window, window), sigma)
    mu_y = cv2.GaussianBlur(y, (window, window), sigma)
    mu_x2, mu_y2, mu_xy = mu_x ** 2, mu_y ** 2, mu_x * mu_y

    sigma_x2 = cv2.GaussianBlur(x * x, (window, window), sigma) - mu_x2
    sigma_y2 = cv2.GaussianBlur(y * y, (window, window), sigma) - mu_y2
    sigma_xy = cv2.GaussianBlur(x * y, (window, window), sigma) - mu_xy

    numerator = (2 * mu_xy + c1) * (2 * sigma_xy + c2)
    denominator = (mu_x2 + mu_y2 + c1) * (sigma_x2 + sigma_y2 + c2)
    return float(np.mean(numerator / denominator))


def colorfulness(img: np.ndarray) -> float:
    """Hasler & Süsstrunk (2003) — ยิ่งสูงยิ่งสีสด"""
    rgb = np.clip(img, 0.0, 1.0).astype(np.float32) * 255.0
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    rg = red - green
    yb = 0.5 * (red + green) - blue
    std_rg, std_yb = float(rg.std()), float(yb.std())
    mean_rg, mean_yb = float(rg.mean()), float(yb.mean())
    return float(np.sqrt(std_rg ** 2 + std_yb ** 2) + 0.3 * np.sqrt(mean_rg ** 2 + mean_yb ** 2))


class LpipsMetric:
    """LPIPS แบบ lazy — ถ้าไม่ได้ติดตั้ง `lpips` จะคืน None แทนการล้ม"""

    def __init__(self, net: str = "alex", device: str = "cpu"):
        try:
            import lpips
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "ต้องติดตั้ง lpips + torch ก่อน (pip install lpips torch) "
                f"— {exc}"
            ) from exc
        self._torch = torch
        self._model = lpips.LPIPS(net=net).to(device).eval()
        self._device = device
        self.net = net

    def __call__(self, a: np.ndarray, b: np.ndarray) -> float:
        torch = self._torch
        tensors = []
        for img in (a, b):
            arr = np.ascontiguousarray(np.clip(img, 0.0, 1.0).transpose(2, 0, 1))
            tensor = torch.from_numpy(arr).float() * 2.0 - 1.0
            tensors.append(tensor.unsqueeze(0).to(self._device))
        with torch.no_grad():
            return float(self._model(tensors[0], tensors[1]).item())


# ---------- จับคู่ไฟล์ ----------
def find_pairs(input_dir: Path, reference_dir: Path) -> list[tuple[Path, Path]]:
    refs = {
        path.stem.lower(): path
        for path in sorted(reference_dir.iterdir())
        if path.suffix.lower() in IMAGE_EXTS and path.is_file()
    }
    pairs = []
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTS or not path.is_file():
            continue
        ref = refs.get(path.stem.lower())
        if ref is None:
            print(f"  ข้าม {path.name}: ไม่พบภาพอ้างอิงชื่อเดียวกัน")
            continue
        pairs.append((path, ref))
    return pairs


def align(result: np.ndarray, reference: np.ndarray, max_side: int) -> tuple[np.ndarray, np.ndarray]:
    """ปรับขนาดให้ตรงกัน (metrics ต้องเทียบพิกเซลต่อพิกเซล)"""
    height, width = reference.shape[:2]
    if max_side and max(height, width) > max_side:
        scale = max_side / max(height, width)
        width, height = max(int(round(width * scale)), 1), max(int(round(height * scale)), 1)
        reference = cv2.resize(reference, (width, height), interpolation=cv2.INTER_AREA)
    if result.shape[:2] != (height, width):
        result = cv2.resize(result, (width, height), interpolation=cv2.INTER_AREA)
    return result, reference


# ---------- main ----------
def main() -> int:
    parser = argparse.ArgumentParser(description="วัด PSNR/SSIM/LPIPS ของ pipeline")
    parser.add_argument("--input", required=True, help="โฟลเดอร์ภาพต้นทาง (เสีย/ฟิล์ม)")
    parser.add_argument("--reference", required=True, help="โฟลเดอร์ภาพอ้างอิง")
    parser.add_argument("--preset", default="color_negative", choices=sorted(PRESETS))
    parser.add_argument("--overrides", default="{}", help='JSON เช่น \'{"denoise":0.4,"face":null}\'')
    parser.add_argument("--out", default="backend/outputs/eval", help="โฟลเดอร์เก็บผลและรายงาน")
    parser.add_argument("--max-side", type=int, default=0, help="ย่อภาพก่อนวัด (0 = ไม่ย่อ)")
    parser.add_argument("--crop-border", action="store_true", help="ตัดขอบฟิล์มก่อนประมวลผล")
    parser.add_argument("--lpips", action="store_true", help="เพิ่ม LPIPS (ต้องติดตั้ง lpips)")
    parser.add_argument("--no-pipeline", action="store_true",
                        help="วัดภาพต้นทางเทียบอ้างอิงโดยไม่รัน pipeline (ค่าตั้งต้นก่อนฟื้นฟู)")
    parser.add_argument("--limit", type=int, default=0, help="จำกัดจำนวนภาพ (0 = ทั้งหมด)")
    parser.add_argument("--cpu", action="store_true", help="บังคับใช้ CPU")
    args = parser.parse_args()

    if args.cpu:
        import os

        os.environ["FILM_RESTORE_CPU"] = "1"

    input_dir = Path(args.input)
    reference_dir = Path(args.reference)
    if not input_dir.is_dir() or not reference_dir.is_dir():
        print("ต้องระบุ --input และ --reference เป็นโฟลเดอร์ที่มีอยู่")
        return 2

    try:
        overrides = json.loads(args.overrides or "{}")
    except json.JSONDecodeError as exc:
        print(f"--overrides ต้องเป็น JSON: {exc}")
        return 2
    if not isinstance(overrides, dict):
        print("--overrides ต้องเป็น JSON object")
        return 2

    pairs = find_pairs(input_dir, reference_dir)
    if args.limit:
        pairs = pairs[: args.limit]
    if not pairs:
        print("ไม่พบคู่ภาพที่ชื่อตรงกัน")
        return 1

    out_dir = Path(args.out)
    (out_dir / "result").mkdir(parents=True, exist_ok=True)

    lpips_metric = None
    lpips_note = "ไม่ได้เปิดใช้"
    if args.lpips:
        try:
            lpips_metric = LpipsMetric(device=gpu_mod.detect().device)
            lpips_note = f"lpips net={lpips_metric.net}"
        except RuntimeError as exc:
            lpips_note = f"ใช้ไม่ได้: {exc}"
            print(f"! LPIPS {lpips_note}")

    info = gpu_mod.detect()
    rows = []
    print(f"preset={args.preset} device={info.device} overrides={overrides} ภาพ {len(pairs)} คู่")

    for index, (input_path, reference_path) in enumerate(pairs, start=1):
        started = time.perf_counter()
        source, bits = load_image(input_path)
        if args.crop_border:
            source = crop_film_border(source)
        reference, _ = load_image(reference_path)

        if args.no_pipeline:
            result_image = source
            warnings: list[str] = []
        else:
            engine = Engine(args.preset, overrides, gpu=info, source_bits=bits)
            result = engine.run(source)
            if result.image is None:
                print(f"[{index}/{len(pairs)}] {input_path.name}: ไม่มีผลลัพธ์")
                continue
            result_image = result.image
            warnings = result.warnings

        aligned_result, aligned_ref = align(result_image, reference, args.max_side)
        save_image(out_dir / "result" / f"{input_path.stem}.png", aligned_result)

        row = {
            "image": input_path.name,
            "reference": reference_path.name,
            "width": int(aligned_ref.shape[1]),
            "height": int(aligned_ref.shape[0]),
            "psnr": round(psnr(aligned_result, aligned_ref), 3),
            "ssim": round(ssim(aligned_result, aligned_ref), 4),
            "lpips": None,
            "colorfulness": round(colorfulness(aligned_result), 2),
            "colorfulness_ref": round(colorfulness(aligned_ref), 2),
            "seconds": round(time.perf_counter() - started, 1),
            "warnings": "; ".join(warnings),
        }
        if lpips_metric is not None:
            row["lpips"] = round(lpips_metric(aligned_result, aligned_ref), 4)
        rows.append(row)
        print(
            f"[{index}/{len(pairs)}] {row['image']}: PSNR {row['psnr']:.2f} dB, "
            f"SSIM {row['ssim']:.4f}"
            + (f", LPIPS {row['lpips']:.4f}" if row["lpips"] is not None else "")
            + f", colorfulness {row['colorfulness']:.1f}"
        )

    if not rows:
        print("ไม่มีผลลัพธ์ให้สรุป")
        return 1

    columns = list(rows[0].keys())
    with open(out_dir / "metrics.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "preset": "(ไม่รัน pipeline)" if args.no_pipeline else args.preset,
        "overrides": overrides,
        "device": info.as_dict(),
        "crop_border": args.crop_border,
        "max_side": args.max_side,
        "lpips": lpips_note,
        "count": len(rows),
        "mean": {
            key: round(float(np.mean([row[key] for row in rows if row[key] is not None])), 4)
            for key in ("psnr", "ssim", "lpips", "colorfulness")
            if any(row[key] is not None for row in rows)
        },
        "images": rows,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    mean = summary["mean"]
    print(
        f"\nเฉลี่ย {len(rows)} ภาพ: PSNR {mean.get('psnr', float('nan')):.2f} dB, "
        f"SSIM {mean.get('ssim', float('nan')):.4f}"
        + (f", LPIPS {mean['lpips']:.4f}" if "lpips" in mean else "")
        + f", colorfulness {mean.get('colorfulness', float('nan')):.1f}"
    )
    print(f"รายงาน: {out_dir / 'metrics.csv'} และ {out_dir / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
