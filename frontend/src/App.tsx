import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchHealth, fetchPresets, previewImage, runRestore } from "./api";
import ImportCard from "./components/ImportCard";
import type { ItemView } from "./components/ImportCard";
import ResultCard from "./components/ResultCard";
import SettingsCard from "./components/SettingsCard";
import type { Health, JobResult, PresetsResponse, Settings } from "./types";

type Item = ItemView & { file: File; result?: JobResult };

const FALLBACK_SETTINGS: Settings = {
  invert: "color",
  color_fix: true,
  color_fix_strength: 0.5,
  scratch: true,
  scratch_strength: 0.6,
  denoise: 0.5,
  colorize: false,
  colorize_strength: 0.8,
  upscale: 2,
  face: 0.7,
  invert_gamma: 1,
  final_wb: 0.3,
  final_contrast: 0.15,
  final_saturation: 0.1,
  final_grain: 0.02,
};

let seq = 0;
const nextId = () => `item-${Date.now().toString(36)}-${(seq += 1)}`;

function toSettings(raw: Record<string, unknown>, base: Settings): Settings {
  const num = (value: unknown, fallback: number) =>
    typeof value === "number" && Number.isFinite(value) ? value : fallback;
  const bool = (value: unknown, fallback: boolean) => (typeof value === "boolean" ? value : fallback);
  const invert = raw.invert === "color" || raw.invert === "bw" ? raw.invert : null;

  return {
    invert,
    color_fix: bool(raw.color_fix, base.color_fix),
    color_fix_strength: num(raw.color_fix_strength, base.color_fix_strength),
    scratch: bool(raw.scratch, base.scratch),
    scratch_strength: num(raw.scratch_strength, base.scratch_strength),
    denoise: num(raw.denoise, base.denoise),
    colorize: bool(raw.colorize, base.colorize),
    colorize_strength: num(raw.colorize_strength, base.colorize_strength),
    upscale: num(raw.upscale, base.upscale),
    face: raw.face === null || raw.face === undefined ? null : num(raw.face, 0.7),
    invert_gamma: num(raw.invert_gamma, base.invert_gamma),
    final_wb: num(raw.final_wb, base.final_wb),
    final_contrast: num(raw.final_contrast, base.final_contrast),
    final_saturation: num(raw.final_saturation, base.final_saturation),
    final_grain: num(raw.final_grain, base.final_grain),
  };
}

function deviceLine(health: Health | null): string {
  const gpu = health?.gpu;
  if (!gpu) return "กำลังตรวจเครื่อง…";
  if (gpu.backend === "cpu") return "CPU";
  const name = gpu.name.replace("NVIDIA GeForce ", "");
  return `${name} · ${gpu.total_vram_gb.toFixed(1)} GB · ${gpu.fp16 ? "fp16" : "fp32"}`;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [presets, setPresets] = useState<PresetsResponse | null>(null);
  const [presetKey, setPresetKey] = useState("color_negative");
  const [settings, setSettings] = useState<Settings>(FALLBACK_SETTINGS);
  const [cropBorder, setCropBorder] = useState(true);
  const [items, setItems] = useState<Item[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const previewToken = useRef(0);

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null));
    fetchPresets()
      .then((data) => {
        setPresets(data);
        setSettings({ ...FALLBACK_SETTINGS, ...data.defaults["color_negative"] });
      })
      .catch(() => setPresets(null));
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const activeItem = items.find((item) => item.id === activeId) ?? null;
  const activeResult = activeItem?.result ?? null;
  const [stageIndex, setStageIndex] = useState(-1);

  // เปลี่ยนภาพที่เลือก → กลับไปดูผลลัพธ์สุดท้าย
  useEffect(() => {
    setStageIndex(-1);
  }, [activeId]);

  // พรีวิวสด ๆ บนภาพย่อ: หน่วง 350ms แล้วยิงไป /api/preview (เฉพาะขั้นเบา)
  useEffect(() => {
    const item = items.find((entry) => entry.id === activeId);
    if (!item || item.status === "running") {
      return;
    }
    const token = (previewToken.current += 1);
    const timer = window.setTimeout(() => {
      previewImage(item.file, { preset: presetKey, settings, cropBorder })
        .then((url) => {
          if (previewToken.current !== token) {
            URL.revokeObjectURL(url);
            return;
          }
          setPreviewUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return url;
          });
        })
        .catch(() => {
          /* พรีวิวพลาดไม่เป็นไร — ยังใช้ภาพต้นฉบับได้ */
        });
    }, 350);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, items.length, presetKey, settings, cropBorder]);

  const presetList = useMemo(
    () => (presets ? Object.keys(presets.labels).map((key) => ({ key, label: presets.labels[key] })) : []),
    [presets],
  );

  const choosePreset = useCallback(
    (key: string) => {
      setPresetKey(key);
      const defaults = presets?.defaults[key];
      if (defaults) setSettings({ ...FALLBACK_SETTINGS, ...defaults });
    },
    [presets],
  );

  const patchSettings = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
  }, []);

  const addFiles = useCallback((files: File[]) => {
    const created: Item[] = files.map((file) => ({
      id: nextId(),
      name: file.name,
      size: file.size,
      status: "queued",
      thumb: URL.createObjectURL(file),
      file,
    }));
    setItems((prev) => [...prev, ...created]);
    setActiveId((prev) => prev ?? created[0]?.id ?? null);
  }, []);

  const removeItem = useCallback((id: string) => {
    setItems((prev) => {
      const target = prev.find((item) => item.id === id);
      if (target) URL.revokeObjectURL(target.thumb);
      const next = prev.filter((item) => item.id !== id);
      setActiveId((current) => (current === id ? (next[0]?.id ?? null) : current));
      return next;
    });
  }, []);

  const applySettings = useCallback((result: JobResult) => {
    setPresetKey(result.preset);
    setSettings((prev) => toSettings(result.settings as unknown as Record<string, unknown>, prev));
    setNotice(`ใช้ค่าจากภาพที่ประมวลผลแล้ว (โหมด ${result.preset_label})`);
  }, []);

  const importSettingsFile = useCallback(async (file: File) => {
    try {
      const data = JSON.parse(await file.text());
      const raw = data?.settings && typeof data.settings === "object" ? data.settings : data;
      if (typeof data?.preset === "string" && presets?.defaults[data.preset]) {
        setPresetKey(data.preset);
      }
      if (raw && typeof raw === "object") {
        setSettings((prev) => toSettings(raw as Record<string, unknown>, prev));
        setNotice(`โหลดการตั้งค่าจาก ${file.name} แล้ว`);
      } else {
        setNotice("ไฟล์นี้ไม่มีการตั้งค่าให้โหลด");
      }
    } catch {
      setNotice(`อ่านไฟล์ ${file.name} ไม่ได้ (ต้องเป็น JSON)`);
    }
  }, [presets]);

  const runAll = useCallback(async () => {
    if (running || items.length === 0) return;
    const pending = items.filter((item) => item.status !== "done");
    const targets = pending.length ? pending : items;

    setRunning(true);
    setProgress(0);
    setProgressText("กำลังเริ่ม…");
    let finished = 0;

    for (const target of targets) {
      setActiveId(target.id);
      setItems((prev) =>
        prev.map((item) => (item.id === target.id ? { ...item, status: "running", error: undefined } : item)),
      );
      try {
        const payload = await runRestore(
          target.file,
          { preset: presetKey, settings, cropBorder },
          (value, message) => {
            setProgress((finished + value) / targets.length);
            setProgressText(`${finished + 1}/${targets.length} · ${message}`);
          },
        );
        setItems((prev) =>
          prev.map((item) => (item.id === target.id ? { ...item, status: "done", result: payload } : item)),
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setItems((prev) =>
          prev.map((item) => (item.id === target.id ? { ...item, status: "error", error: message } : item)),
        );
      }
      finished += 1;
      setProgress(finished / targets.length);
    }
    setRunning(false);
    setProgressText("");
  }, [cropBorder, items, presetKey, running, settings]);

  const results = useMemo(
    () =>
      items
        .filter((item) => item.result)
        .map((item) => {
          const result = item.result as JobResult;
          const last = result.stages[result.stages.length - 1];
          return {
            id: item.id,
            thumb: last ? last.url : result.result_url,
            label: item.name,
            active: item.id === activeId,
          };
        }),
    [activeId, items],
  );

  const modelsReady = health ? health.models.filter((model) => model.downloaded).length : 0;
  const modelsTotal = health ? health.models.length : 0;

  return (
    <div className="app">
      <header className="page-head">
        <div>
          <div className="kicker">Local Studio</div>
          <h1>ห้องฟื้นฟูภาพฟิล์ม</h1>
          <p>กลับสี ซ่อมรอย ลดเกรน คืนใบหน้า — ภาพทั้งหมดประมวลผลในเครื่องคุณ</p>
        </div>
        <div className="pills">
          <span className="pill">
            <span className="dot" />
            ไม่ใช้คลาวด์
          </span>
          <span className="pill">
            <span className="dot" />
            {deviceLine(health)}
          </span>
          <span className="pill">
            <span className="dot" />
            โมเดลพร้อม {modelsReady}/{modelsTotal}
          </span>
          <a className="pill pill--link" href="/classic/">
            หน้าเดิม (Gradio)
          </a>
        </div>
      </header>

      {notice && <div className="notice">{notice}</div>}

      <main className="grid">
        <div className="col col--left">
          <ImportCard
            items={items}
            activeId={activeId}
            previewUrl={previewUrl}
            running={running}
            progress={progress}
            progressText={progressText}
            onAdd={addFiles}
            onRemove={removeItem}
            onSelect={setActiveId}
            onRun={runAll}
          />
          <SettingsCard
            presets={presetList}
            presetKey={presetKey}
            note={presets?.notes[presetKey] ?? ""}
            settings={settings}
            cropBorder={cropBorder}
            onPreset={choosePreset}
            onChange={patchSettings}
            onCrop={setCropBorder}
            onImport={importSettingsFile}
          />
        </div>

        <div className="col col--right">
          <ResultCard
            result={activeResult}
            stageIndex={stageIndex}
            running={running}
            progress={progress}
            progressText={progressText}
            error={activeItem?.error ?? null}
            results={results}
            onStage={setStageIndex}
            onPickResult={setActiveId}
            onApplySettings={applySettings}
          />
        </div>
      </main>
    </div>
  );
}
