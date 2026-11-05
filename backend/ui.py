"""หน้าเว็บด้วย Gradio (เฟส 1)

- เลือกประเภทฟิล์มแล้วค่าเริ่มต้นของทุกขั้นเปลี่ยนตาม
- เปิด/ปิดแต่ละขั้นและปรับความแรงได้
- สไลเดอร์เทียบก่อน/หลัง + ดูผลทีละขั้น
"""

from __future__ import annotations

from .core import gpu as gpu_mod
from .core.image_io import crop_film_border, load_image, resize_max
from .core.model_manager import get_manager
from .pipeline.engine import Engine
from .pipeline.presets import PRESET_LABELS, PRESET_NOTES, PRESETS, get_preset

_INVERT_CHOICES = [("สี (C-41)", "color"), ("ขาวดำ", "bw"), ("ไม่กลับสี", "none")]
_UPSCALE_CHOICES = [("ปิด", 1), ("x2", 2), ("x4", 4)]


def _status_markdown(info: gpu_mod.GPUInfo) -> str:
    if info.backend == "cpu":
        device = "CPU"
    else:
        device = f"{info.name} ({info.total_vram_gb:.1f} GB) — {info.device}"
        device += " · fp16" if info.fp16 else " · fp32"
        if info.tile_size:
            device += f" · tile {info.tile_size}px"

    models = get_manager().status()
    ready = [m["label"] for m in models if m["downloaded"]]
    pending = len(models) - len(ready)
    model_line = f"โมเดลพร้อมใช้: {', '.join(ready)}" if ready else "ยังไม่มี weights ในเครื่อง"
    if pending:
        model_line += f" · อีก {pending} โมเดลจะดาวน์โหลดตอนใช้ครั้งแรก"

    lines = [f"**อุปกรณ์:** {device}", f"**{model_line}**"]
    lines += [f"- {note}" for note in info.notes]
    return "\n".join(lines)


def build_ui(info: gpu_mod.GPUInfo | None = None):
    import gradio as gr

    gpu = info or gpu_mod.detect()
    default = get_preset("color_negative")

    with gr.Blocks(title="Film Restore") as demo:
        gr.Markdown(
            "# Film Restore\n"
            "นำเข้าภาพจากฟิล์มหรือภาพพิมพ์เก่า แล้วกลับสี ลบรอย ลดเกรน ใส่สี และเพิ่มความคมชัด"
        )
        gr.Markdown(_status_markdown(gpu))

        with gr.Row():
            with gr.Column(scale=1):
                # ใช้ gr.File + ตัวอย่างภาพที่แปลงเป็น 8-bit เอง
                # เพราะเบราว์เซอร์แสดง TIFF 16-bit / RAW ไม่ได้ (จะขึ้นเป็นแถบขาด)
                image_in = gr.File(label="ภาพต้นฉบับ (JPG / TIFF 16-bit / RAW)")
                preview = gr.Image(
                    label="ตัวอย่างภาพ", height=240, interactive=False, type="numpy"
                )
                preset = gr.Radio(
                    choices=[(PRESET_LABELS[key], key) for key in PRESETS],
                    value="color_negative",
                    label="ประเภทต้นฉบับ",
                )
                preset_note = gr.Markdown(f"*{PRESET_NOTES['color_negative']}*")
                crop = gr.Checkbox(value=True, label="ครอปขอบฟิล์ม/ขอบสแกน")

                with gr.Accordion("กลับสีและแก้สี", open=True):
                    invert = gr.Radio(
                        choices=_INVERT_CHOICES, value="color", label="กลับสีเนกาทีฟ"
                    )
                    color_fix = gr.Checkbox(value=default["color_fix"], label="แก้สีซีด/เพี้ยน")
                    cf_strength = gr.Slider(
                        0, 1, default["color_fix_strength"], step=0.05, label="ความแรงแก้สี"
                    )

                with gr.Accordion("ซ่อมภาพ", open=True):
                    scratch = gr.Checkbox(value=default["scratch"], label="ลบรอยขีดข่วน/ฝุ่น")
                    scratch_strength = gr.Slider(
                        0, 1, default["scratch_strength"], step=0.05, label="ความไวการตรวจรอย"
                    )
                    denoise = gr.Slider(0, 1, default["denoise"], step=0.05, label="ลดเกรน")

                with gr.Accordion("ใส่สี / ขยายภาพ / ใบหน้า", open=True):
                    colorize = gr.Checkbox(value=default["colorize"], label="ใส่สี (เฉพาะภาพขาวดำ)")
                    colorize_strength = gr.Slider(
                        0, 1, default["colorize_strength"], step=0.05, label="ความแรงใส่สี"
                    )
                    upscale = gr.Radio(
                        choices=_UPSCALE_CHOICES, value=default["upscale"], label="เพิ่มความละเอียด"
                    )
                    face = gr.Checkbox(value=default["face"] is not None, label="ฟื้นฟูใบหน้า")
                    face_fidelity = gr.Slider(
                        0, 1, default["face"] or 0.7, step=0.05,
                        label="fidelity ใบหน้า (สูง = เหมือนต้นฉบับ)",
                    )

                with gr.Accordion("ปรับแต่งขั้นสุดท้าย", open=False):
                    final_wb = gr.Slider(0, 1, default["final_wb"], step=0.05, label="white balance")
                    final_contrast = gr.Slider(
                        0, 0.6, default["final_contrast"], step=0.05, label="contrast"
                    )
                    final_grain = gr.Slider(
                        0, 0.08, default["final_grain"], step=0.005, label="เติมเกรน"
                    )

                run_btn = gr.Button("ฟื้นฟูภาพ", variant="primary")

            with gr.Column(scale=2):
                compare = gr.ImageSlider(label="ก่อน / หลัง (ลากเส้นเทียบ)", height=460)
                stages = gr.Gallery(label="ผลแต่ละขั้น", columns=3, height=280)
                log = gr.Textbox(label="บันทึกการทำงาน", lines=8, max_lines=16)

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
            """อ่านภาพด้วยตัวอ่านของโปรแกรม (รองรับ TIFF/RAW) แล้วคืนสำเนา 8-bit ไว้แสดง"""
            if not image_path:
                return None
            try:
                img, _ = load_image(image_path)
            except Exception as exc:
                raise gr.Error(f"เปิดภาพไม่ได้: {exc}") from exc
            thumb, _ = resize_max(img, 900)
            return thumb

        image_in.change(show_preview, inputs=[image_in], outputs=[preview])

        def run_ui(image_path, preset_key, crop_border, invert_mode, cf_on, cf_s,
                   scratch_on, scratch_s, denoise_s, colorize_on, colorize_s,
                   upscale_scale, face_on, fidelity, wb, contrast, grain,
                   progress=gr.Progress()):
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
                source, progress=lambda frac, msg: progress(0.05 + frac * 0.9, desc=msg)
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
