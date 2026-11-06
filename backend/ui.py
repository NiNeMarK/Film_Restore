"""หน้าเว็บด้วย Gradio (เฟส 1 — เน้นภาพ)

- หัวเรื่องแถวเดียว + ป้ายสถานะเครื่อง/โมเดลชิดขวา
- สองคอลัมน์: ซ้าย = นำเข้าภาพ + ตั้งค่า, ขวา = ผลลัพธ์ (สไลเดอร์เทียบก่อน/หลัง)
  จัดให้ทั้งหน้าแสดงในหน้าต่างเดสก์ท็อป 1320×900 ได้โดยไม่ต้องเลื่อนจอ
- ตั้งค่าที่ไม่ค่อยได้แตะพับไว้ใน accordion, log ย่อเหลือ 3 บรรทัด
- โทนฟิล์มอุ่น ๆ (cream / warm gray / amber)
"""

from __future__ import annotations

from pathlib import Path

from .core import gpu as gpu_mod
from .core.image_io import crop_film_border, load_image, resize_max
from .core.model_manager import get_manager
from .pipeline.engine import Engine
from .pipeline.presets import PRESET_LABELS, PRESET_NOTES, PRESETS, get_preset

# หน้าเว็บ React (เฟส 3) — ถ้า build ไว้แล้วจะโชว์ลิงก์ไปที่ /app
_REACT_APP = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "index.html"

_INVERT_CHOICES = [("สี (C-41)", "color"), ("ขาวดำ", "bw"), ("ไม่กลับสี", "none")]
_UPSCALE_CHOICES = [("ปิด", 1), ("x2", 2), ("x4", 4)]

CSS = """
body { background: #f5ebe0 !important; }

.gradio-container {
  max-width: 1400px !important;
  margin: 0 auto !important;
  padding: 8px 20px 8px !important;
  background: transparent !important;
  font-family: "IBM Plex Serif Thai", "Noto Serif Thai", "Sarabun",
               "Segoe UI", "Leelawadee UI", serif !important;
}

/* สองคอลัมน์: ซ้ายนำเข้า/ตั้งค่า, ขวาผลลัพธ์ — ชิดบนและไม่ยืดสูงตามกัน */
.fr-main { gap: 12px !important; align-items: flex-start !important; }
.fr-side { gap: 10px !important; min-width: 0 !important; }
.fr-card { gap: 8px !important; }
/* Gradio ใส่ padding ให้ .main เอง — ตัดออกเพื่อให้เนื้อหาชิดขอบบน */
.gradio-container > .main, .gradio-container .app { padding: 0 !important; gap: 0 !important; }

/* แถวหัวการ์ดไม่ต้องมี padding ของ Gradio (ประหยัดความสูง) */
.fr-headwrap { padding: 0 !important; min-height: 0 !important; }
.fr-headwrap > div, .fr-headwrap .prose { margin: 0 !important; }
.fr-card .html-container { padding: 0 !important; min-height: 0 !important; }
.fr-import { gap: 10px !important; align-items: stretch !important; max-height: 104px; }

/* ---------- header ---------- */
.fr-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px 8px;
  border-bottom: 1px solid #d4c4a8;
  margin-bottom: 6px;
}
.fr-kicker {
  font-size: .62rem;
  letter-spacing: .2em;
  text-transform: uppercase;
  font-weight: 700;
  color: #b8956a;
}
.fr-head h1 {
  margin: 0 0 2px;
  padding: 0;
  font-size: 1.32rem;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -.01em;
  color: #2c1810 !important;
  font-family: "IBM Plex Serif Thai", "Noto Serif Thai", serif !important;
}
.fr-head p { margin: 0; font-size: .78rem; color: #8b7355 !important; }
.fr-head-pills { display: flex; flex-wrap: wrap; gap: 6px; padding-top: 4px; }
.fr-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border: 1px solid #d4c4a8;
  border-radius: 2px;
  background: #f5ebe0;
  font-size: .72rem;
  font-weight: 600;
  color: #5a4530;
  white-space: nowrap;
  font-family: "IBM Plex Sans Thai", "Noto Sans Thai", sans-serif !important;
}
.fr-pill .dot { width: 6px; height: 6px; border-radius: 50%; background: #c89b4b; }
.fr-pill.warn .dot { background: #a0522d; }
.fr-pill-link { text-decoration: none; color: #a07050 !important; border-style: dashed; }
.fr-pill-link:hover { background: #efe1c8; }

/* ---------- cards ---------- */
.fr-card {
  background: #faf3e6 !important;
  border: 1px solid #d4c4a8 !important;
  border-radius: 4px !important;
  padding: 10px 14px !important;
  box-shadow: 0 4px 12px rgba(90, 60, 30, .12), 0 1px 3px rgba(90, 60, 30, .08) !important;
}
.fr-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e0d0b8;
}
.fr-card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: .92rem;
  font-weight: 700;
  color: #2c1810;
  font-family: "IBM Plex Serif Thai", "Noto Serif Thai", serif !important;
}
.fr-card-title svg { width: 15px; height: 15px; color: #a07050; flex: none; }
.fr-hint { font-size: .7rem; color: #9a7f5c; }

/* บัตรที่มีกรดฟิล์มอุ่น ๆ */
.fr-card--warm {
  color: #2c1810 !important;
  background: linear-gradient(180deg, #f5ebe0 0%, #efe1c8 50%, #e8d4b8 100%) !important;
  border: 1px solid #c8b898 !important;
}
.fr-card--warm .fr-card-title { color: #2c1810; }
.fr-card--warm .fr-hint { color: #7a5f3a; }

#fr-run {
  border: 0 !important;
  border-radius: 2px !important;
  background: #5a3a2a !important;
  font-weight: 700 !important;
  letter-spacing: .02em;
  box-shadow: 0 4px 8px rgba(60, 40, 20, .3) !important;
  color: #f5ebe0 !important;
  transition: transform .15s ease, filter .15s ease;
  font-size: 1rem !important;
  padding: 12px 28px !important;
  font-family: "IBM Plex Serif Thai", "Noto Serif Thai", serif !important;
}
#fr-run:hover { transform: translateY(-2px); filter: brightness(1.05); box-shadow: 0 6px 12px rgba(60, 40, 20, .4) !important; }

/* ---------- uploads ---------- */
.fr-uploader { min-height: 0 !important; height: auto !important; max-height: none !important; }
.fr-uploader > .wrap {
  background: #f0e4d0 !important;
  border: 1px dashed #b8a080 !important;
  border-radius: 2px !important;
  min-height: 0 !important;
}
/* Gradio ตั้งความสูงช่องลากไฟล์ไว้ 240px — ย่อลงให้พอดีการ์ด
   และซ่อนข้อความ "Drop File Here" ข้างใน (ใช้ label ด้านบนแทน) */
.fr-uploader .upload-container {
  min-height: 96px !important;
  height: 96px !important;
  background: #f0e4d0 !important;
  border: 1px dashed #b8a080 !important;
}
.fr-uploader .upload-container .wrap { display: none !important; }
.fr-uploader .wrap:hover { background: #e8d8c0 !important; }
.fr-preview { border-radius: 2px !important; border: 1px solid #d4c4a8 !important; }
.fr-preview .image-container { min-height: 0 !important; }

/* ---------- controls ---------- */
.fr-card .form { gap: 8px !important; }
.fr-preset .wrap { gap: 2px 16px !important; }
.fr-preset label { font-size: .84rem !important; }
.fr-preset label > span { padding: 3px 0 !important; }
.fr-note {
  font-size: .74rem !important;
  color: #8b7355 !important;
  margin: -2px 0 2px !important;
  line-height: 1.5 !important;
}

/* ---------- labels, sliders, accordions ---------- */
.fr-card label > span, .fr-card .fr-label {
  font-size: .8rem !important;
  font-weight: 600 !important;
  color: #5a4530 !important;
}
.fr-card input[type="range"] { accent-color: #c89b4b; }
.fr-card input[type="range"]::-webkit-slider-thumb { accent-color: #a07050; }
.fr-card .block {
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
}
.fr-card .form { gap: 6px !important; }
.fr-card .label-wrap {
  padding: 4px 2px !important;
  border-top: 1px solid #e0d0b8;
  font-size: .82rem !important;
  font-weight: 600 !important;
  color: #2c1810 !important;
}
.fr-card .label-wrap:hover { color: #a07050 !important; }

/* accordion */
.gr-accordion-header { border-bottom: 1px solid #e0d0b8 !important; padding: 4px 0 !important; }
.gr-accordion-header:hover { color: #a07050 !important; }

/* ---------- results ---------- */
.fr-card .image-slider {
  border: 1px solid #d4c4a8 !important;
  border-radius: 2px !important;
  overflow: hidden;
  background: #f0e4d0 !important;
}
/* ตอนยังไม่มีผลลัพธ์: ซ่อนไอคอนจาง ๆ แล้วเขียนคำใบ้กลางกรอบแทน */
.fr-card--compare { position: relative !important; }
.fr-card--compare:not(:has(img[src]))::after {
  content: "ผลลัพธ์จะแสดงที่นี่ — เลือกภาพแล้วกด «ฟื้นฟูภาพ»";
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b39a76;
  font-size: .92rem;
  letter-spacing: .01em;
  pointer-events: none;
}
/* แถบผลแต่ละขั้นซ่อนไว้จนกว่าจะมีผลจริง */
.fr-card--plus__gallery:not(:has(img[src])) { display: none !important; }
.fr-card--plus__gallery ::-webkit-scrollbar { display: none !important; }
.fr-card--plus__gallery .grid-wrap { overflow-x: hidden !important; }
.fr-card .image-slider::-webkit-scrollbar { display: none !important; }
/* ซ่อนไอคอน placeholder ของสไลเดอร์ตอนยังไม่มีภาพ (ใช้ข้อความของเราแทน) */
.fr-card--compare .empty { background: transparent !important; }
.fr-card--compare .empty .icon { display: none !important; }
.fr-card .gallery-item { border-radius: 2px !important; border: 1px solid #d4c4a8 !important; }
.fr-card .caption { font-size: .7rem !important; color: #7a6344 !important; }
.fr-log textarea {
  background: #f0e4d0 !important;
  border: 1px solid #d4c4a8 !important;
  border-radius: 2px !important;
  color: #5a4530 !important;
  font-family: "JetBrains Mono", "Cascadia Mono", ui-monospace, monospace !important;
  font-size: .76rem !important;
  line-height: 1.7 !important;
}
.fr-log { border-color: #d4c4a8 !important; }

/* film grain texture ใน background */
body::before {
  content: "";
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.04'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: -1;
  opacity: 0.5;
}

footer, .footer { display: none !important; }
"""

_ICON_UPLOAD = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 16V4m0 0L8 8m4-4 4 4"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></svg>'
)
_ICON_SETTINGS = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4 7h9M17 7h3M4 12h3M11 12h9M4 17h9M17 17h3"/>'
    '<circle cx="15" cy="7" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="15" cy="17" r="2"/></svg>'
)
_ICON_IMAGE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="4" width="18" height="16" rx="4"/><circle cx="9" cy="10" r="1.8"/>'
    '<path d="m4 18 5-5 4 4 3-3 4 4"/></svg>'
)


def _card_head(icon: str, title: str, hint: str = "") -> str:
    """หัวการ์ด 1 บรรทัด: ไอคอน + ชื่อ + คำใบ้ชิดขวา"""
    return (
        '<div class="fr-card-head">'
        f'<span class="fr-card-title">{icon}<span>{title}</span></span>'
        f'<span class="fr-hint">{hint}</span>'
        "</div>"
    )


def _head_html(info: gpu_mod.GPUInfo) -> str:
    models = get_manager().status()
    ready = sum(1 for model in models if model["downloaded"])
    total = len(models)

    device_line = (
        f"{info.name.replace('NVIDIA GeForce ', '')} · {info.total_vram_gb:.1f} GB · "
        f"{'fp16' if info.fp16 else 'fp32'}"
        if info.backend != "cpu"
        else "CPU"
    )
    pills = [
        '<span class="fr-pill"><span class="dot"></span>ไม่ใช้คลาวด์</span>',
        f'<span class="fr-pill"><span class="dot"></span>{device_line}</span>',
        f'<span class="fr-pill"><span class="dot"></span>โมเดลพร้อม {ready}/{total}</span>',
    ]
    if info.backend == "cpu":
        pills.insert(1, '<span class="fr-pill warn"><span class="dot"></span>CPU Mode</span>')
    if _REACT_APP.is_file():
        pills.append(
            '<a class="fr-pill fr-pill-link" href="/app/" target="_blank" '
            'rel="noreferrer">หน้าใหม่ (React) →</a>'
        )

    return (
        '<div class="fr-head"><div>'
        '<div class="fr-kicker">Local Studio</div>'
        "<h1>ห้องฟื้นฟูภาพฟิล์ม</h1>"
        "<p>กลับสี ซ่อมรอย ลดเกรน คืนใบหน้า — ภาพทั้งหมดประมวลผลในเครื่องคุณ</p>"
        "</div>"
        '<div class="fr-head-pills">' + "".join(pills) + "</div></div>"
        "<div style='margin-top:12px;'></div>"
    )


def theme():
    """ธีมสำหรับ Gradio — ใช้ css ร่วมด้วย"""
    import gradio as gr

    return gr.themes.Soft(
        primary_hue=gr.themes.colors.amber,
        secondary_hue=gr.themes.colors.amber,
        neutral_hue=gr.themes.colors.gray,
        radius_size=gr.themes.sizes.radius_lg,
        font=[
            gr.themes.GoogleFont("IBM Plex Sans Thai"),
            "Noto Sans Thai",
            "Segoe UI",
            "sans-serif",
        ],
    )


def build_ui(info: gpu_mod.GPUInfo | None = None):
    import gradio as gr

    gpu = info or gpu_mod.detect()
    default = get_preset("color_negative")

    with gr.Blocks(title="Film Restore") as demo:
        gr.HTML(_head_html(gpu))

        # สองคอลัมน์: ซ้าย = นำเข้าภาพ + ตั้งค่า, ขวา = ผลลัพธ์ — เห็นครบในจอเดียว
        with gr.Row(elem_classes="fr-main", equal_height=False):
            with gr.Column(scale=4, min_width=360, elem_classes="fr-side"):
                # ---- ภาพต้นฉบับ + ปุ่มฟื้นฟู ----
                with gr.Column(elem_classes="fr-card fr-card--warm"):
                    gr.HTML(
                        _card_head(_ICON_UPLOAD, "ภาพต้นฉบับ", "JPG · TIFF · RAW"),
                        elem_classes="fr-headwrap",
                    )
                    # ช่องอัปโหลดกับภาพย่อวางเคียงกัน ประหยัดความสูง
                    with gr.Row(elem_classes="fr-import"):
                        image_in = gr.File(
                            label="ลากไฟล์มาวาง หรือคลิกเพื่อเลือก",
                            file_count="single",
                            scale=3,
                            elem_classes="fr-uploader",
                        )
                        preview = gr.Image(
                            show_label=False,
                            height=96,
                            interactive=False,
                            type="numpy",
                            scale=2,
                            visible=False,      # ซ่อนไว้ก่อน แสดงเมื่อเลือกไฟล์แล้ว
                            elem_classes="fr-preview",
                        )
                    run_btn = gr.Button(
                        "ฟื้นฟูภาพ", variant="primary", size="lg", elem_id="fr-run"
                    )

                # ---- ตั้งค่าขั้นตอน (ยุบ/ขยายได้) ----
                with gr.Column(elem_classes="fr-card"):
                    gr.HTML(
                        _card_head(_ICON_SETTINGS, "ตั้งค่าขั้นตอน", "เลือกโหมดแล้วปรับได้"),
                        elem_classes="fr-headwrap",
                    )
                    preset = gr.Radio(
                        choices=[(PRESET_LABELS[key], key) for key in PRESETS],
                        value="color_negative",
                        show_label=False,
                        container=False,
                        elem_classes="fr-preset",
                    )
                    preset_note = gr.Markdown(
                        f"*{PRESET_NOTES['color_negative']}*", elem_classes="fr-note"
                    )
                    crop = gr.Checkbox(value=True, label="ครอปขอบฟิล์ม/ขอบสแกน")

                    with gr.Accordion("กลับสีและแก้สี", open=False):
                        invert = gr.Radio(
                            choices=_INVERT_CHOICES, value="color", label="กลับสีเนกาทีฟ"
                        )
                        color_fix = gr.Checkbox(
                            value=default["color_fix"], label="แก้สีซีด/เพี้ยน"
                        )
                        cf_strength = gr.Slider(
                            0, 1, default["color_fix_strength"], step=0.05,
                            label="ความแรงแก้สี",
                        )

                    with gr.Accordion("ซ่อมภาพ", open=False):
                        scratch = gr.Checkbox(
                            value=default["scratch"], label="ลบรอยขีดข่วน/ฝุ่น"
                        )
                        scratch_strength = gr.Slider(
                            0, 1, default["scratch_strength"], step=0.05,
                            label="ความไวการตรวจรอย",
                        )
                        denoise = gr.Slider(
                            0, 1, default["denoise"], step=0.05, label="ลดเกรน"
                        )

                    with gr.Accordion("ใส่สี / ขยายภาพ / ใบหน้า", open=False):
                        colorize = gr.Checkbox(
                            value=default["colorize"], label="ใส่สี (เฉพาะภาพขาวดำ)"
                        )
                        colorize_strength = gr.Slider(
                            0, 1, default["colorize_strength"], step=0.05,
                            label="ความแรงใส่สี",
                        )
                        upscale = gr.Radio(
                            choices=_UPSCALE_CHOICES,
                            value=default["upscale"],
                            label="เพิ่มความละเอียด",
                        )
                        face = gr.Checkbox(
                            value=default["face"] is not None, label="ฟื้นฟูใบหน้า"
                        )
                        face_fidelity = gr.Slider(
                            0, 1, default["face"] or 0.7, step=0.05,
                            label="fidelity ใบหน้า (สูง = เหมือนต้นฉบับ)",
                        )

                    with gr.Accordion("ปรับแต่งขั้นสุดท้าย", open=False):
                        final_wb = gr.Slider(
                            0, 1, default["final_wb"], step=0.05, label="white balance"
                        )
                        final_contrast = gr.Slider(
                            0, 0.6, default["final_contrast"], step=0.05, label="contrast"
                        )
                        final_grain = gr.Slider(
                            0, 0.08, default["final_grain"], step=0.005, label="เติมเกรน"
                        )

            # ---- ขวา: ผลลัพธ์ ----
            with gr.Column(scale=7, min_width=520, elem_classes="fr-side"):
                with gr.Column(elem_classes="fr-card"):
                    gr.HTML(
                        _card_head(
                            _ICON_IMAGE,
                            "ผลลัพธ์",
                            "ลากเส้นกลางภาพเพื่อเทียบก่อน/หลัง",
                        ),
                        elem_classes="fr-headwrap",
                    )
                    compare = gr.ImageSlider(
                        label="",
                        height=360,
                        container=False,
                        elem_classes="fr-card--compare",
                    )
                    stages = gr.Gallery(
                        label="",
                        columns=8,
                        height=70,
                        object_fit="cover",
                        container=False,
                        elem_classes="fr-card--plus__gallery",
                    )
                    log = gr.Textbox(
                        label="",
                        show_label=False,
                        lines=2,
                        max_lines=6,
                        placeholder="ยังไม่มีผลลัพธ์ — เลือกภาพทางซ้ายแล้วกด «ฟื้นฟูภาพ»",
                        elem_classes="fr-log",
                    )

        # ---- เฟสสายงาน (ไม่แสดงบน UI — ใช้ภายใน) ----
        preset_inputs = [
            invert,
            color_fix,
            cf_strength,
            scratch,
            scratch_strength,
            denoise,
            colorize,
            colorize_strength,
            upscale,
            face,
            face_fidelity,
        ]

        def apply_preset(key: str):
            values = get_preset(key)
            invert_value = values["invert"] or "none"
            return [
                gr.update(value=invert_value, interactive=values["invert"] is not None),
                gr.update(value=values["color_fix"]),
                gr.update(value=values["color_fix_strength"]),
                gr.update(value=values["scratch"]),
                gr.update(value=values["scratch_strength"]),
                gr.update(value=values["denoise"]),
                gr.update(value=values["colorize"]),
                gr.update(value=values["colorize_strength"]),
                gr.update(value=values["upscale"]),
                gr.update(value=values["face"] is not None),
                gr.update(value=values["face"] or 0.7),
                gr.update(value=f"*{PRESET_NOTES.get(key, '')}*"),
            ]

        preset.change(
            apply_preset,
            inputs=[preset],
            outputs=preset_inputs + [preset_note],
        )

        def show_preview(image_path):
            """แสดงภาพย่อเมื่อเลือกไฟล์แล้ว (ซ่อน компонентเมื่อยังไม่มีไฟล์)"""
            if not image_path:
                return gr.update(value=None, visible=False)
            try:
                img, _ = load_image(image_path)
            except Exception as exc:
                raise gr.Error(f"เปิดภาพไม่ได้: {exc}") from exc
            thumb, _ = resize_max(img, 900)
            return gr.update(value=thumb, visible=True)

        image_in.change(show_preview, inputs=[image_in], outputs=[preview])

        def run_ui(
            image_path,
            preset_key,
            crop_border,
            invert_mode,
            cf_on,
            cf_s,
            scratch_on,
            scratch_s,
            denoise_s,
            colorize_on,
            colorize_s,
            upscale_scale,
            face_on,
            fidelity,
            wb,
            contrast,
            grain,
            progress=gr.Progress(),
        ):
            if not image_path:
                raise gr.Error("กรุณาเลือกภาพก่อนกดฟื้นฟู")

            overrides = dict(
                invert=None if invert_mode == "none" else invert_mode,
                color_fix=bool(cf_on),
                color_fix_strength=float(cf_s),
                scratch=bool(scratch_on),
                scratch_strength=float(scratch_s),
                denoise=float(denoise_s),
                colorize=bool(colorize_on),
                colorize_strength=float(colorize_s),
                upscale=int(upscale_scale),
                face=float(fidelity) if face_on else None,
                final_wb=float(wb),
                final_contrast=float(contrast),
                final_grain=float(grain),
            )

            progress(0.02, desc="อ่านไฟล์ภาพ…")
            img, bits = load_image(image_path)
            source = crop_film_border(img) if crop_border else img

            engine = Engine(preset_key, overrides, gpu=gpu, source_bits=bits)
            result = engine.run(
                source,
                progress=lambda frac, msg: progress(0.05 + frac * 0.9, desc=msg),
            )

            after = result.image
            gallery = [
                (stage.image, f"{index + 1}. {stage.label} · {stage.seconds:.1f}s")
                for index, stage in enumerate(result.stages)
            ]

            lines = [
                f"โหมด: {PRESET_LABELS.get(preset_key, preset_key)}",
                f"ต้นฉบับ: {img.shape[1]}×{img.shape[0]} px, {bits}-bit",
                f"ผลลัพธ์: {after.shape[1]}×{after.shape[0]} px",
                f"ใช้เวลา: {result.elapsed:.1f} วินาที",
                "อุปกรณ์: "
                + (
                    "CPU"
                    if result.meta["device"] == "cpu"
                    else f"{result.meta['gpu']} ({result.meta['device']})"
                ),
                "",
            ]
            for stage in result.stages:
                lines.append(f"[{stage.seconds:5.1f}s] {stage.label}: {stage.note}")
            if result.warnings:
                lines += ["", "คำเตือน:"] + [f"- {warning}" for warning in result.warnings]

            return (source, after), gallery, "\n".join(lines)

        run_btn.click(
            run_ui,
            inputs=[
                image_in,
                preset,
                crop,
                invert,
                color_fix,
                cf_strength,
                scratch,
                scratch_strength,
                denoise,
                colorize,
                colorize_strength,
                upscale,
                face,
                face_fidelity,
                final_wb,
                final_contrast,
                final_grain,
            ],
            outputs=[compare, stages, log],
        )

    return demo
