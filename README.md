# Film Restore

ฟื้นฟูภาพจากฟิล์มและภาพพิมพ์เก่า: กลับสีเนกาทีฟ แก้สี ลบรอย ลดเกรน ใส่สี ขยายภาพ และฟื้นฟูใบหน้า
ประมวลผลบนเครื่องผู้ใช้ (GPU ถ้ามี, CPU แทนได้) — ดูแผนฉบับเต็มที่ [docs/Film_Restore.md](docs/Film_Restore.md)

## รัน

```bash
pip install -r requirements.txt
python backend/main.py            # เปิด http://localhost:7860
python backend/main.py --host 0.0.0.0   # ให้มือถือในวง Wi-Fi เดียวกันเข้าได้
python desktop.py                 # โหมดหน้าต่างโปรแกรม (ต้องติดตั้ง pywebview)
```

ถ้าไม่มี GPU หรือยังไม่ติดตั้งโมเดล โปรแกรมยังใช้งานได้: ขั้นที่ต้องใช้โมเดลจะถูกข้าม
พร้อมแจ้งเตือนในหน้าจอ ส่วน upscale จะใช้ Lanczos แทน Real-ESRGAN

## ส่วนประกอบ

| ไฟล์ | หน้าที่ |
|---|---|
| `backend/main.py` | FastAPI (`/api/health`, `/api/presets`, `/api/restore`) + เสิร์ฟ Gradio ที่ `/` |
| `backend/ui.py` | หน้า Gradio: เลือกโหมด, เปิด/ปิดแต่ละขั้น, สไลเดอร์เทียบก่อน/หลัง, ดูผลทีละขั้น |
| `backend/pipeline/engine.py` | ร้อยขั้นตาม preset, เก็บผลทุกขั้น, บันทึกคำเตือนเมื่อโมเดลไม่พร้อม |
| `backend/pipeline/film_invert.py` | กลับสีเนกาทีฟ + ตัดสีส้มฐานฟิล์ม (density = log10(base/img)) |
| `backend/pipeline/color_fix.py` | แก้สีซีด/เพี้ยน + ปรับแต่งขั้นสุดท้าย (white balance, contrast, เกรน) |
| `backend/pipeline/scratch.py` | ตรวจรอยด้วย top-hat/black-hat + ซ่อมด้วย LaMa หรือ OpenCV |
| `backend/pipeline/denoise.py` | ลดเกรนแบบ NLM พร้อมเติมรายละเอียดความถี่สูงกลับ |
| `backend/pipeline/colorize.py` | ใส่สีด้วย DDColor: ใส่สีบนภาพย่อแล้วขยาย chroma กลับทับ luma เดิม |
| `backend/pipeline/upscale.py` | Real-ESRGAN x2/x4 (สำรอง: Lanczos + unsharp) |
| `backend/pipeline/face.py` | GFPGAN v1.4 พร้อมตัวปรับ fidelity |
| `backend/core/gpu.py` | ตรวจ VRAM แล้วเลือก fp16 / ขนาด tile / เปิดปิด Diffusion |
| `backend/core/model_manager.py` | ดาวน์โหลด weights ครั้งแรก, lazy load, ใช้ไฟล์ในเครื่องได้ถ้ามีอยู่แล้ว |

weights เก็บที่ `backend/models/` (ไม่อยู่ใน git) — วางไฟล์ `.pth` เองได้ถ้าดาวน์โหลดช้า
เปลี่ยนโฟลเดอร์ด้วย env `FILM_RESTORE_MODELS`

## API

```bash
curl http://localhost:7860/api/health

curl -X POST http://localhost:7860/api/restore \
  -F "file=@scan.jpg" \
  -F "preset=color_negative" \
  -F 'overrides={"denoise":0.4,"upscale":2,"face":null}' \
  -F "crop_border=true"
```

ผลลัพธ์: URL ของภาพแต่ละขั้น + `settings.json` ที่บันทึกค่าที่ใช้กับภาพนั้น (ไว้กลับมาแก้ภายหลัง)
ไฟล์อยู่ใน `backend/outputs/<job>/`

## สถานะเทียบกับแผน

- **เฟส 1:** film_invert, color_fix, engine + presets, Gradio UI, ต่อ DDColor / Real-ESRGAN / GFPGAN เรียบร้อย
  (CodeFormer ยังไม่ต่อ — ต้องติดตั้งจาก GitHub และใช้ไลเซนส์ S-Lab สำหรับใช้ส่วนตัว)
- **เฟส 2:** scratch (ตรวจรอย + LaMa), denoise, gpu.py (VRAM/fp16/tiling) เรียบร้อย;
  SCUNet ยังไม่ต่อ (ใช้ NLM แทนชั่วคราวตามที่ระบุใน denoise.py)
- **เฟส 3–5:** React frontend, แพ็ก .exe, พู่กันระบุสี / Diffusion ยังไม่ได้ทำ
