"""สร้างชุดทดสอบตายตัวสำหรับวัดคุณภาพ (แผนข้อ 9)

ชุดภาพอ้างอิงใช้ Kodak PhotoCD 24 ภาพ (768×512) ซึ่งเป็นชุดมาตรฐานที่ใช้ในงาน
image restoration — ครอบคลุมคน ทิวทัศน์ อาคาร และภาพในร่ม
จากนั้นสร้างภาพ "เสีย" แบบกำหนดได้ (fixed seed) สองชุดจากภาพเดียวกัน:

  testset/ref/            ต้นฉบับ (ภาพอ้างอิง)
  testset/faded/in/       ภาพพิมพ์สีซีด + เกรน + รอยขีด (ใช้ preset faded_color)
  testset/negative/in/    เนกาทีฟสี (ใช้ preset color_negative)

ทุกครั้งที่รันสคริปต์นี้จะได้ภาพชุดเดิมและ degradations ชุดเดิม (seed คงที่)
จึงเทียบผลข้ามรอบได้

รัน:
  python backend/tools/make_testset.py                # ดาวน์โหลด + สร้างชุดทดสอบ
  python backend/tools/make_testset.py --limit 8      # ทดลองเร็วก่อน
  python backend/tools/make_testset.py --skip-download  # ใช้ ref ที่มีอยู่แล้ว
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SOURCE_URL = "http://r0k.us/graphics/kodak/kodak/kodim{n:02d}.png"
IMAGE_COUNT = 24
DEFAULT_OUT = Path("testset")
SEED = 20260101

PROFILES = {
    "faded": {
        "preset": "faded_color",
        "description": "ภาพพิมพ์สีซีด + สีเพี้ยน + เกรน + รอยขีดข่วนเล็กน้อย",
    },
    "negative": {
        "preset": "color_negative",
        "description": "เนกาทีฟสี (กลับสี + มาสก์ส้มฐานฟิล์ม) + เกรน",
    },
}


def download_refs(ref_dir: Path, count: int) -> None:
    ref_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        target = ref_dir / f"kodim{index:02d}.png"
        if target.exists() and target.stat().st_size > 50_000:
            print(f"  มีอยู่แล้ว {target.name}")
            continue
        url = SOURCE_URL.format(n=index)
        print(f"  ดาวน์โหลด {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "film-restore/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
        if len(data) < 50_000 or not data.startswith(b"\x89PNG"):
            raise RuntimeError(f"ไฟล์ที่ได้ไม่ใช่ PNG ที่สมบูรณ์: {url} ({len(data)} ไบต์)")
        target.write_bytes(data)


def degrade_faded(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """จำลองภาพพิมพ์ที่จาง: คอนทราสต์ต่ำ สีเพี้ยน มีเกรนและรอยขีด"""
    out = img * 0.72 + 0.24
    out[..., 0] *= 1.04          # เอียงไปทางเหลือง/แดงเล็กน้อย
    out[..., 2] *= 0.95
    out = cv2.GaussianBlur(out, (0, 0), 0.6)
    out = out + rng.normal(0.0, 0.015, out.shape).astype(np.float32)

    height, width = out.shape[:2]
    for _ in range(6):  # รอยขีดข่วนบาง ๆ
        x0 = int(rng.integers(0, width))
        y0 = int(rng.integers(0, height))
        x1 = int(np.clip(x0 + rng.normal(0, width * 0.12), 0, width - 1))
        y1 = int(np.clip(y0 + rng.normal(height * 0.7, height * 0.25), 0, height - 1))
        shade = 0.92 if rng.random() < 0.5 else 0.12
        cv2.line(out, (x0, y0), (x1, y1), (shade, shade, shade), 1, cv2.LINE_AA)
    return np.clip(out, 0.0, 1.0)


def degrade_negative(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """จำลองเนกาทีฟสี: กลับสีแล้วใส่มาสก์ส้มฐานฟิล์ม"""
    out = (1.0 - img) * np.array([0.98, 0.90, 0.80], dtype=np.float32)
    out = out + np.array([0.10, 0.06, 0.02], dtype=np.float32)
    out = out + rng.normal(0.0, 0.012, out.shape).astype(np.float32)
    return np.clip(out, 0.0, 1.0)


DEGRADERS = {"faded": degrade_faded, "negative": degrade_negative}


def to_u8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def build_sets(out_dir: Path, count: int) -> dict:
    ref_dir = out_dir / "ref"
    refs = sorted(ref_dir.glob("kodim*.png"))[:count]
    if not refs:
        raise RuntimeError(f"ไม่พบภาพอ้างอิงใน {ref_dir}")

    manifest = {"source": "Kodak PhotoCD (r0k.us/graphics/kodak)", "seed": SEED, "profiles": {}}
    profile_ids = {name: index for index, name in enumerate(PROFILES, start=1)}
    for name, info in PROFILES.items():
        in_dir = out_dir / name / "in"
        in_dir.mkdir(parents=True, exist_ok=True)
        for ref_path in refs:
            img = cv2.cvtColor(cv2.imread(str(ref_path)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            # seed ต่อไฟล์ + ต่อโปรไฟล์ เพื่อให้ผลคงที่ไม่ว่าจะรันทีละกี่ภาพ
            rng = np.random.default_rng([SEED, int(ref_path.stem[-2:]), profile_ids[name]])
            degraded = DEGRADERS[name](img, rng)
            suffix = ".jpg" if name == "faded" else ".png"
            Path(in_dir / f"{ref_path.stem}{suffix}").parent.mkdir(parents=True, exist_ok=True)
            if suffix == ".jpg":
                cv2.imwrite(
                    str(in_dir / f"{ref_path.stem}{suffix}"),
                    cv2.cvtColor(to_u8(degraded), cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 85],
                )
            else:
                cv2.imwrite(
                    str(in_dir / f"{ref_path.stem}{suffix}"),
                    cv2.cvtColor(to_u8(degraded), cv2.COLOR_RGB2BGR),
                )
        manifest["profiles"][name] = {
            "preset": info["preset"],
            "description": info["description"],
            "images": len(refs),
        }
        print(f"  สร้าง {name}/in {len(refs)} ภาพ")

    # reference ใช้ชื่อ stem เดียวกัน (นามสกุลต่างกันได้)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างชุดทดสอบตายตัว + ภาพเสียจำลอง")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="โฟลเดอร์เก็บชุดทดสอบ")
    parser.add_argument("--limit", type=int, default=IMAGE_COUNT,
                        help=f"จำนวนภาพ (สูงสุด {IMAGE_COUNT})")
    parser.add_argument("--skip-download", action="store_true", help="ไม่ต้องดาวน์โหลด ref")
    args = parser.parse_args()

    count = max(1, min(args.limit, IMAGE_COUNT))
    out_dir = Path(args.out)
    if not args.skip_download:
        print(f"ดาวน์โหลดภาพอ้างอิง {count} ภาพจาก Kodak PhotoCD")
        download_refs(out_dir / "ref", count)
    manifest = build_sets(out_dir, count)

    print("\nเสร็จแล้ว — ชุดทดสอบอยู่ที่", out_dir.resolve())
    for name, info in manifest["profiles"].items():
        print(f"  {name:9s} preset={info['preset']:15s} {info['images']} ภาพ")
    print(
        "\nวัดผล เช่น:\n"
        f"  python backend/tools/evaluate.py --input {out_dir}/faded/in "
        f"--reference {out_dir}/ref --preset faded_color --out backend/outputs/eval/faded --lpips"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
