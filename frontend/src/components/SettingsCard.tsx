import type { Settings } from "../types";
import { SettingsIcon } from "./icons";

type Props = {
  presets: { key: string; label: string }[];
  presetKey: string;
  note: string;
  settings: Settings;
  cropBorder: boolean;
  onPreset: (key: string) => void;
  onChange: (patch: Partial<Settings>) => void;
  onCrop: (value: boolean) => void;
};

type SliderFieldProps = {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
  format?: (value: number) => string;
};

function SliderField({ label, value, min = 0, max = 1, step = 0.05, onChange, format }: SliderFieldProps) {
  return (
    <label className="field field--slider">
      <span className="field-label">
        {label}
        <em>{format ? format(value) : value.toFixed(2)}</em>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function CheckField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="field field--check">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export default function SettingsCard({
  presets,
  presetKey,
  note,
  settings,
  cropBorder,
  onPreset,
  onChange,
  onCrop,
}: Props) {
  const faceOn = settings.face !== null;

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          <SettingsIcon />
          ตั้งค่าขั้นตอน
        </h2>
        <span className="hint">เลือกโหมดแล้วปรับได้</span>
      </header>

      <div className="presets" role="radiogroup" aria-label="ประเภทต้นฉบับ">
        {presets.map((preset) => (
          <button
            key={preset.key}
            type="button"
            role="radio"
            aria-checked={preset.key === presetKey}
            className={`preset${preset.key === presetKey ? " is-on" : ""}`}
            onClick={() => onPreset(preset.key)}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <p className="preset-note">{note}</p>

      <CheckField label="ครอปขอบฟิล์ม/ขอบสแกน" checked={cropBorder} onChange={onCrop} />

      <details className="group">
        <summary>กลับสีและแก้สี</summary>
        <div className="group-body">
          <label className="field">
            <span className="field-label">กลับสีเนกาทีฟ</span>
            <select
              value={settings.invert ?? "none"}
              onChange={(event) =>
                onChange({ invert: event.target.value === "none" ? null : (event.target.value as "color" | "bw") })
              }
            >
              <option value="color">สี (C-41)</option>
              <option value="bw">ขาวดำ</option>
              <option value="none">ไม่กลับสี</option>
            </select>
          </label>
          <CheckField label="แก้สีซีด/เพี้ยน" checked={settings.color_fix} onChange={(v) => onChange({ color_fix: v })} />
          <SliderField
            label="ความแรงแก้สี"
            value={settings.color_fix_strength}
            onChange={(v) => onChange({ color_fix_strength: v })}
          />
        </div>
      </details>

      <details className="group">
        <summary>ซ่อมภาพ</summary>
        <div className="group-body">
          <CheckField label="ลบรอยขีดข่วน/ฝุ่น" checked={settings.scratch} onChange={(v) => onChange({ scratch: v })} />
          <SliderField
            label="ความไวการตรวจรอย"
            value={settings.scratch_strength}
            onChange={(v) => onChange({ scratch_strength: v })}
          />
          <SliderField label="ลดเกรน" value={settings.denoise} onChange={(v) => onChange({ denoise: v })} />
        </div>
      </details>

      <details className="group">
        <summary>ใส่สี / ขยายภาพ / ใบหน้า</summary>
        <div className="group-body">
          <CheckField
            label="ใส่สี (เฉพาะภาพขาวดำ)"
            checked={settings.colorize}
            onChange={(v) => onChange({ colorize: v })}
          />
          <SliderField
            label="ความแรงใส่สี"
            value={settings.colorize_strength}
            onChange={(v) => onChange({ colorize_strength: v })}
          />
          <label className="field">
            <span className="field-label">เพิ่มความละเอียด</span>
            <select value={settings.upscale} onChange={(event) => onChange({ upscale: Number(event.target.value) })}>
              <option value={1}>ปิด</option>
              <option value={2}>x2</option>
              <option value={4}>x4</option>
            </select>
          </label>
          <CheckField
            label="ฟื้นฟูใบหน้า"
            checked={faceOn}
            onChange={(v) => onChange({ face: v ? 0.7 : null })}
          />
          <SliderField
            label="fidelity ใบหน้า (สูง = เหมือนต้นฉบับ)"
            value={settings.face ?? 0.7}
            onChange={(v) => onChange({ face: v })}
          />
        </div>
      </details>

      <details className="group">
        <summary>ปรับแต่งขั้นสุดท้าย</summary>
        <div className="group-body">
          <SliderField label="white balance" value={settings.final_wb} onChange={(v) => onChange({ final_wb: v })} />
          <SliderField
            label="contrast"
            value={settings.final_contrast}
            max={0.6}
            onChange={(v) => onChange({ final_contrast: v })}
          />
          <SliderField
            label="เติมเกรน"
            value={settings.final_grain}
            max={0.08}
            step={0.005}
            onChange={(v) => onChange({ final_grain: v })}
          />
        </div>
      </details>
    </section>
  );
}
