"""หน้าเว็บด้วย Gradio (เฟส 1 — เน้นภาพ)

- ภาพต้นฉบับย่อไว้	 OpenGL|
- ไม่มี sidebar/navigator
- ช่องอุปกรณ์/โมเดลยุบรวมเป็นแถวย่อยท้ายหัว
- ผลลัพธ์ใหญ่ในกลาง, รูปที่เลือกไว้แสดงใต้ผลลัพธ์
- โทนฟิล์มอุ่น ๆ (cream / warm gray / amber)
"""

from __future__ import annotations

from .core import gpu as gpu_mod
from .core.image_io import crop_film_border, load_image, resize_max
from .core.model_manager import get_manager
from .pipeline.engine import Engine
from .pipeline.presets import PRESET_LABELS, PRESET_NOTES, PRESETS, get_preset

_INVERT_CHOICES = [("สี (C-41)", "color"), ("ขาวดำ", "bw"), ("ไม่กลับสี", "none")]
_UPSCALE_CHOICES = [("ปิด", 1), ("x2", 2), ("x4", 4)]

CSS = """
body { background: #f5ebe0 !important; }

.gradio-container {
  max-width: 1400px !important;
  margin: 0 auto !important;
  padding: 20px 24px 32px !important;
  background: transparent !important;
  font-family: "IBM Plex Serif Thai", "Noto Serif Thai", "Sarabun",
               "Segoe UI", "Leelawadee UI", serif !important;
}

.fr-shell { gap: 20px !important; align-items: flex-start !important; }
.fr-main { gap: 20px !important; }

/* ---------- header ---------- */
.fr-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 0 2px 6px;
  border-bottom: 1px solid #d4c4a8;
  margin-bottom: 18px;
}
.fr-kicker {
  font-size: .62rem;
  letter-spacing: .2em;
  text-transform: uppercase;
  font-weight: 700;
  color: #b8956a;
}
.fr-head h1 {
  margin: 2px 0 4px;
  padding: 0;
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: -.01em;
  color: #2c1810 !important;
  font-family: "IBM Plex Serif Thai", "Noto Serif Thai", serif !important;
}
.fr-head p { margin: 0; font-size: .85rem; color: #8b7355 !important; }
.fr-head-pills { display: flex; flex-wrap: wrap; gap: 6px; padding-top: 4px; }
.fr-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
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

/* ---------- cards ---------- */
.fr-card {
  background: #faf3e6 !important;
  border: 1px solid #d4c4a8 !important;
  border-radius: 4px !important;
  padding: 16px 18px !important;
  box-shadow: 0 4px 12px rgba(90, 60, 30, .12), 0 1px 3px rgba(90, 60, 30, .08) !important;
}
.fr-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e0d0b8;
}
.fr-card-title { font-size: .95rem; font-weight: 700; color: #2c1810; font-family: "IBM Plex Serif Thai", "Noto Serif Thai", serif !important; }
.fr-hint { font-size: .72rem; color: #9a7f5c; }

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
.fr-uploader .wrap { background: #f0e4d0 !important; border: 1px dashed #b8a080 !important; border-radius: 2px !important; }
.fr-uploader .wrap:hover { background: #e8d8c0 !important; }
.fr-preview { border-radius: 2px !important; border: 1px solid #d4c4a8 !important; }

/* ---------- controls ---------- */
.fr-card label > span, .fr-card .fr-label {
  font-size: .8rem !important;
  font-weight: 600 !important;
  color: #5a4530 !important;
}
.fr-card input[type="range"] { accent-color: #c89b4b; }
.fr-card input[type="range"]::-webkit-slider-thumb { accent-color: #a07050; }
.fr-card .block { background: transparent !important; border: 0 !important; box-shadow: none !important; }
.fr-card .label-wrap {
  padding: 12px 2px !important;
  border-top: 1px solid #e0d0b8;
  font-size: .84rem !important;
  font-weight: 600 !important;
  color: #2c1810 !important;
}
.fr-card .label-wrap:hover { color: #a07050 !important; }

/* accordion */
.gr-accordion-header { border-bottom: 1px solid #e0d0b8 !important; padding: 10px 0 !important; }
.gr-accordion-header:hover { color: #a07050 !important; }

/* ---------- results ---------- */
.fr-card .image-slider {
  border: 1px solid #d4c4a8 !important;
  border-radius: 2px !important;
  overflow: hidden;
  background: #f0e4d0 !important;
}
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
_ICON_LOGO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="4" width="18" height="16" rx="4"/><path d="M7 4v16M17 4v16"/>'
    '<circle cx="12" cy="12" r="2.2"/></svg>'
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
_ICON_LOG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="4" width="18" height="16" rx="4"/><path d="m7 10 3 2-3 2M13 14h4"/></svg>'
)


def _scroll_to(target: str) -> str:
    return (
        "document.getElementById('"
        + target
        + "').scrollIntoView({behavior:'smooth',block:'start'})"
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

    IMG_H_Q = 620  # ความสูงกรอบเปรียบเทียบก่อน/หลัง (กว้างสัดส่วนภาพ)

    with gr.Blocks(title="Film Restore") as demo:
        # ไม่มี gr.Row แยก sidebar — layout เฉียงซ้ายเพียงคอลัมน์เดียว
        with gr.Row(elem_classes="fr-shell"):
            with gr.Column(scale=1):
                gr.HTML(_head_html(gpu))

                # ---- ภาพต้นฉบับ (ย่อมาก) + ปุ่มฟื้นฟู ----
                with gr.Row(elem_classes="fr-shell"):
                    with gr.Column(scale=1, elem_classes="fr-card fr-card--warm"):
                        gr.HTML(
                            '<div class="fr-card-head">'
                            '<span class="fr-card-title">ภาพต้นฉบับ</span>'
                            + '<span class="fr-hint">JPG · TIFF · RAW</span></div>'
                        )
                        image_in = gr.File(
                            label="ลากไฟล์มาวาง หรือคลิกเพื่อเลือก",
                            file_count="single",
                            elem_classes="fr-uploader",
                        )
                        preview = gr.Image(
                            show_label=False,
                            height=80,          # ภาพต้นฉบับย่อมาก
                            interactive=False,
                            type="numpy",
                            elem_classes="fr-preview",
                        )
                        run_btn = gr.Button(
                            "ฟื้นฟูภาพ", variant="primary", size="lg", elem_id="fr-run"
                        )

                # ---- ผลลัพธ์ (ใหญ่) ----
                with gr.Column(elem_classes="fr-card"):
                    gr.HTML(
                        '<div class="fr-card-head">'
                        '<span class="fr-card-title">ผลลัพธ์</span>'
                        + '<span class="fr-hint">กดสลับภาพก่อน/หลังกลางเพื่อเทียบกัน</span></div>'
                    )
                    compare = gr.ImageSlider(
                        label="",
                        height=560,
                        container=False,
                        elem_classes="fr-card--compare",
                    )
                    stages = gr.Gallery(
                        label="",
                        columns=3,
                        height=100,
                        object_fit="cover",
                        container=False,
                        elem_classes="fr-card--plus__gallery",
                    )
                    log = gr.Textbox(
                        label="",
                        show_label=False,
                        lines=4,
                        max_lines=12,
                        elem_classes="fr-log",
                    )

                # ---- ตั้งค่าขั้นตอน (ยุบ/ขยายได้) ----
                with gr.Column(elem_classes="fr-card"):
                    gr.HTML(
                        '<div class="fr-card-head">'
                        '<span class="fr-card-title">ตั้งค่าขั้นตอน</span>'
                        + '<span class="fr-hint">ยุบ/ขยายแต่ละขั้นได้</span></div>'
                    )
                    preset = gr.Radio(
                        choices=[(PRESET_LABELS[key], key) for key in PRESETS],
                        value="color_negative",
                        label="ประเภทต้นฉบับ",
                    )
                    preset_note = gr.Markdown(f"*{PRESET_NOTES['color_negative']}*")
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

                # ---- รูปที่เลือกไว้แล้ว (แสดงใต้ผลลัพธ์) ----
                with gr.Column(scale=5, elem_classes="fr-card fr-card--grade"):
                    gr.HTML(
                        '<div class="fr-card-head">'
                        '<span class="fr-card-title">รูปที่เลือกไว้แล้ว</span>'
                        + '<span class="fr-hint">คลิกรูปเพื่อใช้งานต่อ</span></div>'
                    )
                    graded = gr.Gallery(
                        label="",
                        columns=(1, 2, 3, 4, 5),
                        value=(
                            "خرج_HDR.jpg",
                            "خرج_LQ.jpg",
                            "خرج_HQ.jpg",
                            "خرج_ช่วงกลาง.jpg",
                            "out.jpg",
                        ),
                        height=108,
                        object_fit="cover",
                        preview=True,
                        container=False,
                        elem_classes="fr-card--grade__gallery",
                    )

                # ---- บันทึกการทำงาน ----
                with gr.Column(elem_id="fr-log", elem_classes="fr-card"):
                    gr.HTML(
                        '<div class="fr-card-head">'
                        + '<span class="fr-card-title">บันทึกการทำงาน</span>'
                        + '<span class="fr-hint">โชว์ log ทีละขั้น</span></div>'
                    )
                    log_full = gr.Textbox(
                        label="",
                        show_label=False,
                        lines=7,
                        max_lines=18,
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
            if not image_path:
                return None
            try:
                img, _ = load_image(image_path)
            except Exception as exc:
                raise gr.Error(f"เปิดภาพไม่ได้: {exc}") from exc
            thumb, _ = resize_max(img, 900)
            return thumb

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

        # สายงานเสริม: แท็บผลลัพธ์วิ่งตามรูป "หลัง" ของสไลเดอร์เทียบ (ค่าที่ได้เป็นคู่ before/after)
        def sync_graded(value):
            if isinstance(value, (tuple, list)):
                return value[-1] if value else None
            return value

        compare.change(sync_graded, inputs=[compare], outputs=[graded], show_progress=False)

    return demo
