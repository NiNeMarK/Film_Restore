# Film Restore — แผนการพัฒนา

โปรแกรมนำเข้าภาพจากฟิล์มหรือภาพพิมพ์เก่า แล้วกลับสี ลบรอย ลดเกรน ใส่สี และเพิ่มความคมชัดให้ดูสมจริง

## 1. ขอบเขตโปรเจกต์

| หัวข้อ | รายละเอียด |
|---|---|
| ประเภทต้นฉบับ | รองรับทุกประเภท ผู้ใช้เลือกโหมดเอง |
| ผู้ใช้ | ใช้งานส่วนตัว |
| รูปแบบโปรแกรม | เว็บแอป (localhost) และเดสก์ท็อป |
| การประมวลผล | บนเครื่องผู้ใช้ด้วย GPU (ใช้ CPU แทนได้แต่ช้า) |

**ผลจากเงื่อนไขข้างต้น:**
- ใช้งานส่วนตัว จึงใช้โมเดลที่ห้ามใช้เชิงพาณิชย์ได้ เช่น CodeFormer
- ไม่ต้องมีระบบผู้ใช้ ระบบคิวบนคลาวด์ หรือเซิร์ฟเวอร์ภายนอก
- ใช้โค้ดชุดเดียวกันทั้งเว็บและเดสก์ท็อป

---

## 2. สถาปัตยกรรม

```
┌──────────────────────────────────────────────┐
│  Frontend (Gradio ในช่วงแรก -> React ภายหลัง)  │
│  - เลือกประเภทฟิล์ม  - เปิด/ปิดแต่ละขั้น        │
│  - สไลเดอร์เทียบก่อน/หลัง  - พู่กันระบุสี       │
└───────────────┬──────────────────────────────┘
                │ HTTP / WebSocket (localhost)
┌───────────────▼──────────────────────────────┐
│  Backend: FastAPI (Python) รันบนเครื่องผู้ใช้     │
│  - Pipeline Engine  - Model Manager          │
│  - GPU Manager (fp16, tiling, CPU fallback)  │
└──────────────────────────────────────────────┘
```

- **โหมดเว็บแอป:** รัน backend แล้วเปิด `http://localhost:7860` ใช้จากมือถือหรือแท็บเล็ตในวง Wi-Fi เดียวกันได้
- **โหมดเดสก์ท็อป:** ใช้ pywebview เปิด UI เดิมเป็นหน้าต่างโปรแกรม แล้วแพ็กเป็น .exe ด้วย PyInstaller

---

## 3. Pipeline การประมวลผล

1. **นำเข้าภาพ:** รับไฟล์ RAW, TIFF หรือ JPG แล้วครอปขอบฟิล์ม (OpenCV, rawpy)
2. **กลับสีเนกาทีฟ:** แปลงเนกาทีฟเป็นโพสิทีฟและตัดสีส้มของฐานฟิล์ม (เขียนเอง)
3. **แก้สี:** แก้สีซีดหรือสีเพี้ยนของสไลด์และภาพพิมพ์
4. **ลบรอยขีดข่วนและฝุ่น:** ตรวจหาตำแหน่งที่เสียหายแล้วซ่อมภาพ (inpainting)
5. **ลดนอยส์และเกรน:** ลดเกรนแต่เก็บรายละเอียดไว้
6. **ใส่สี:** ใช้เฉพาะภาพขาวดำ
7. **Upscale:** เพิ่มความละเอียดด้วย super-resolution
8. **ฟื้นฟูใบหน้า:** ปรับระดับ fidelity ได้
9. **ปรับแต่งขั้นสุดท้าย:** white balance, contrast และเติมเกรนเล็กน้อยให้ดูเป็นธรรมชาติ

### 3.1 โหมดตามประเภทฟิล์ม

| ประเภทต้นฉบับ | กลับสี | แก้สี | ลบรอย | ลดเกรน | ใส่สี | Upscale + หน้า |
|---|---|---|---|---|---|---|
| เนกาทีฟขาวดำ | ✓ | – | ✓ | ✓ | ✓ | ✓ |
| เนกาทีฟสี (C-41) | ✓ | ✓ ตัดสีส้มของฐานฟิล์ม | ✓ | ✓ | – | ✓ |
| สไลด์/โพสิทีฟ (E-6) | – | ✓ แก้สีซีดหรือเพี้ยนแดง | ✓ | ✓ | – | ✓ |
| ภาพพิมพ์ขาวดำ | – | – | ✓ รอยพับ รอยฉีก | ✓ | ✓ | ✓ |
| ภาพพิมพ์สีที่ซีด | – | ✓ ฟื้นฟูสี | ✓ | ✓ | ตัวเลือก | ✓ |

ทุกขั้นเปิดหรือปิดได้และปรับความแรงได้ ค่าเริ่มต้นตั้งตามโหมดที่เลือก

### 3.2 โมเดลที่ใช้

| ขั้น | โมเดลหลัก | สำรองหรือขั้นสูง |
|---|---|---|
| ลบรอย | Bringing Old Photos Back to Life (ส่วนตรวจหารอย) + LaMa | – |
| ลดเกรน | SCUNet | Restormer, NAFNet |
| ใส่สี | DDColor | DeOldify, Stable Diffusion + ControlNet |
| Upscale | Real-ESRGAN x2/x4 | SwinIR, HAT |
| ฟื้นฟูใบหน้า | CodeFormer | GFPGAN |

> โหมด Diffusion ให้ผลสมจริงที่สุด แต่ช้ากว่าและอาจเติมรายละเอียดที่ไม่มีในภาพจริง (hallucination)

---

## 4. เทคโนโลยี

- **AI และการประมวลผล:** Python, PyTorch, OpenCV, ONNX Runtime, rawpy
- **Backend:** FastAPI + WebSocket สำหรับแสดงความคืบหน้า
- **Frontend:** Gradio (เฟส 1–2) แล้วเปลี่ยนเป็น React + Vite (เฟส 3 เป็นต้นไป)
- **Desktop:** pywebview + PyInstaller

---

## 5. สเปกเครื่อง

| ระดับ | GPU | สิ่งที่ทำได้ |
|---|---|---|
| ขั้นต่ำ | VRAM 4–6 GB (GTX 1660, RTX 3050) | ทุกขั้นยกเว้น Diffusion โดยใช้ fp16 + tiling |
| แนะนำ | VRAM 8–12 GB (RTX 3060, 4070) | ทุกขั้นได้เร็ว |
| ขั้นสูง | VRAM 16–24 GB (RTX 4080, 4090) | ใช้โหมด Diffusion ได้ |
| ไม่มี GPU | CPU | ใช้ได้แต่ช้า (ราว 1–5 นาทีต่อภาพ) |

โปรแกรมตรวจ VRAM ตอนเปิด แล้วปรับขนาด tile และเปิดหรือปิดฟีเจอร์ให้อัตโนมัติ

---

## 6. โครงสร้างโปรเจกต์

```
film-restore/
├── plan.md
├── backend/
│   ├── main.py              # FastAPI + เสิร์ฟหน้าเว็บ
│   ├── pipeline/
│   │   ├── engine.py        # ร้อยแต่ละขั้นตาม preset
│   │   ├── presets.py       # ค่าเริ่มต้นของแต่ละประเภทฟิล์ม
│   │   ├── film_invert.py   # กลับสีเนกาทีฟ / ตัดสีส้ม
│   │   ├── color_fix.py     # แก้สีซีดของสไลด์และภาพพิมพ์
│   │   ├── scratch.py       # ลบรอย
│   │   ├── denoise.py
│   │   ├── colorize.py
│   │   ├── upscale.py
│   │   └── face.py
│   ├── core/
│   │   ├── model_manager.py # ดาวน์โหลด weights ครั้งแรก + lazy load
│   │   └── gpu.py           # ตรวจ VRAM, fp16, tiling
│   └── models/              # ไฟล์ weights (ไม่เก็บใน git)
├── frontend/                # React (เฟส 3 เป็นต้นไป)
├── desktop.py               # pywebview wrapper
└── requirements.txt
```

---

## 7. โค้ดตั้งต้น

### 7.1 pipeline/film_invert.py

```python
import numpy as np

def detect_film_base(img: np.ndarray) -> np.ndarray:
    """หาสีฐานฟิล์ม (ส่วนที่ไม่ถูกแสง) จากขอบภาพ ซึ่งเป็นส่วนที่สว่างที่สุดในเนกาทีฟ"""
    h, w = img.shape[:2]
    m = max(h, w) // 40
    border = np.concatenate([img[:m].reshape(-1, 3), img[-m:].reshape(-1, 3),
                             img[:, :m].reshape(-1, 3), img[:, -m:].reshape(-1, 3)])
    return np.percentile(border, 99, axis=0)

def invert_color_negative(img: np.ndarray, base=None, gamma=1.0,
                          clip=(0.1, 99.9)) -> np.ndarray:
    """img: float32 RGB 0-1 (ควรสแกนเป็น 16-bit linear)"""
    img = np.clip(img, 1e-6, 1.0)
    base = detect_film_base(img) if base is None else np.asarray(base)
    density = np.log10(base / img)          # ความหนาแน่นเหนือฐานฟิล์ม = ตัดสีส้มออก
    out = np.empty_like(density)
    for c in range(3):                      # ยืดแต่ละช่องสีแยกกัน = แก้ color balance
        lo, hi = np.percentile(density[..., c], clip)
        out[..., c] = (density[..., c] - lo) / (hi - lo + 1e-6)
    return np.clip(out, 0, 1) ** (1 / gamma)

def invert_bw_negative(img: np.ndarray, clip=(0.1, 99.9)) -> np.ndarray:
    gray = img.mean(axis=2) if img.ndim == 3 else img
    pos = 1.0 - gray
    lo, hi = np.percentile(pos, clip)
    return np.clip((pos - lo) / (hi - lo + 1e-6), 0, 1)
```

### 7.2 pipeline/presets.py

```python
PRESETS = {
    "bw_negative":    dict(invert="bw",    color_fix=False, scratch=True, denoise=0.6, colorize=True,  upscale=2, face=0.7),
    "color_negative": dict(invert="color", color_fix=True,  scratch=True, denoise=0.5, colorize=False, upscale=2, face=0.7),
    "slide":          dict(invert=None,    color_fix=True,  scratch=True, denoise=0.4, colorize=False, upscale=2, face=0.7),
    "bw_print":       dict(invert=None,    color_fix=False, scratch=True, denoise=0.5, colorize=True,  upscale=2, face=0.7),
    "faded_color":    dict(invert=None,    color_fix=True,  scratch=True, denoise=0.4, colorize=False, upscale=2, face=0.7),
}
```

---

## 8. แผนพัฒนาเป็นเฟส (คนเดียว ทำนอกเวลา)

| เฟส | เวลาโดยประมาณ | งาน | ผลลัพธ์ |
|---|---|---|---|
| 1. แกนหลัก | 2–3 สัปดาห์ | film_invert, color_fix, ต่อ DDColor + Real-ESRGAN + CodeFormer, UI ด้วย Gradio | ใช้ได้ครบ 5 โหมดแบบพื้นฐาน |
| 2. ฟื้นฟูภาพ | 2–3 สัปดาห์ | ลบรอย, ลดเกรน, GPU manager (fp16 + tiling) | คุณภาพระดับใช้งานจริง |
| 3. UI จริง | 3–4 สัปดาห์ | React: สไลเดอร์เทียบก่อน/หลัง, ดูผลทีละขั้น, พรีวิวบนภาพย่อแบบ real-time, ทำหลายภาพพร้อมกัน | ใช้งานสะดวก |
| 4. เดสก์ท็อป | 1–2 สัปดาห์ | pywebview + PyInstaller, ดาวน์โหลดโมเดลตอนเปิดครั้งแรก | ไฟล์ .exe ติดตั้งได้ |
| 5. ฟีเจอร์ขั้นสูง | ต่อเนื่อง | พู่กันระบุสี, โหมด Diffusion, fine-tune ด้วยภาพไทยในอดีต | ผลสมจริงขึ้น |

**รวม:** ประมาณ 2–3 เดือนจะได้เวอร์ชันที่ใช้งานได้ดี

### Checklist

- [ ] เฟส 1: ตั้งโปรเจกต์ + requirements.txt
- [ ] เฟส 1: film_invert.py (เนกาทีฟสีและขาวดำ)
- [ ] เฟส 1: color_fix.py
- [ ] เฟส 1: ต่อ DDColor
- [ ] เฟส 1: ต่อ Real-ESRGAN
- [ ] เฟส 1: ต่อ CodeFormer
- [ ] เฟส 1: engine.py + presets.py
- [ ] เฟส 1: หน้า Gradio
- [ ] เฟส 2: scratch.py (ตรวจหารอย + LaMa)
- [ ] เฟส 2: denoise.py (SCUNet)
- [ ] เฟส 2: gpu.py (ตรวจ VRAM, fp16, tiling)
- [ ] เฟส 3: Frontend React
- [ ] เฟส 4: แพ็กเป็น .exe
- [ ] เฟส 5: พู่กันระบุสี / Diffusion / fine-tune

---

## 9. การวัดคุณภาพ

- **ตัวชี้วัดเชิงตัวเลข:** PSNR และ SSIM (ใกล้เคียงต้นฉบับ), LPIPS (ความคล้ายตามการรับรู้), Colorfulness score
- **ประเมินด้วยสายตา:** เทียบแบบ blind test กับ Photoshop Neural Filters หรือ MyHeritage
- **ชุดทดสอบตายตัว:** 20–50 ภาพ ครอบคลุมภาพคน ทิวทัศน์ ในอาคาร และภาพที่เสียหายหนัก ใช้ทดสอบซ้ำทุกครั้งที่แก้ pipeline

---

## 10. ความเสี่ยงและข้อควรรู้

- **สีไม่ตรงความจริง:** AI เดาสีได้แต่ไม่รู้สีจริง จึงต้องมีพู่กันระบุสีให้แก้เอง
- **ใบหน้าเพี้ยน:** ต้องมีตัวปรับ fidelity ของ CodeFormer
- **ภาพความละเอียดสูง:** ไฟล์สแกน 6000 px ขึ้นไปต้องใช้ tiling และควรใส่สีบนภาพย่อก่อน แล้วค่อยขยายช่องสีกลับขึ้นไป
- **ไฟล์ต้นฉบับ:** ถ้าทำได้ ควรสแกนเป็น 16-bit TIFF หรือ RAW เพราะไฟล์ JPEG 8-bit จะทำให้สีเป็นแถบหลังกลับสี
- **เก็บต้นฉบับไว้เสมอ:** บันทึกค่าที่ใช้กับแต่ละภาพเป็นไฟล์ .json เพื่อกลับมาแก้ภายหลังได้
- **ขนาดโปรแกรม:** PyTorch รวม CUDA ราว 2–3 GB และโมเดลทั้งหมดอีกราว 1–2 GB
- **ไลเซนส์:** ใช้ส่วนตัวไม่มีปัญหา แต่ถ้าจะแจกหรือขายภายหลัง ต้องเปลี่ยน CodeFormer และตรวจไลเซนส์ทุกโมเดล

---

## 11. ขั้นตอนแรก

1. ติดตั้ง DDColor, Real-ESRGAN และ CodeFormer แล้วลองกับภาพฟิล์มของตัวเอง 10–20 ภาพ
2. ต่อทั้งสามโมเดลเป็นสคริปต์เดียว แล้วครอบด้วย Gradio
3. ดูว่าผลยังอ่อนตรงไหน แล้วจัดลำดับงานในเฟส 2 ตามนั้น