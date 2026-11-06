import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchHealth, fetchPresets, runRestore } from "./api";
import ImportCard from "./components/ImportCard";
import ResultCard from "./components/ResultCard";
import SettingsCard from "./components/SettingsCard";
import type { Health, JobResult, PresetsResponse, Settings } from "./types";

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
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState("");
  const [result, setResult] = useState<JobResult | null>(null);
  const [stageIndex, setStageIndex] = useState(-1);
  const [error, setError] = useState<string | null>(null);
  const lastPreview = useRef<string | null>(null);

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
    if (!file) {
      setPreviewUrl(null);
      if (lastPreview.current) {
        URL.revokeObjectURL(lastPreview.current);
        lastPreview.current = null;
      }
      return;
    }
    const url = URL.createObjectURL(file);
    if (lastPreview.current) URL.revokeObjectURL(lastPreview.current);
    lastPreview.current = url;
    setPreviewUrl(url);
  }, [file]);

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

  const run = useCallback(async () => {
    if (!file || running) return;
    setRunning(true);
    setError(null);
    setProgress(0);
    setProgressText("กำลังเริ่ม…");
    try {
      const payload = await runRestore(
        file,
        { preset: presetKey, settings, cropBorder },
        (value, message) => {
          setProgress(value);
          setProgressText(message);
        },
      );
      setResult(payload);
      setStageIndex(-1);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }, [cropBorder, file, presetKey, running, settings]);

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
          <a className="pill pill--link" href="/">
            หน้าเดิม (Gradio)
          </a>
        </div>
      </header>

      <main className="grid">
        <div className="col col--left">
          <ImportCard
            file={file}
            previewUrl={previewUrl}
            running={running}
            progress={progress}
            progressText={progressText}
            onFile={(next) => {
              setFile(next);
              setError(null);
            }}
            onRun={run}
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
          />
        </div>

        <div className="col col--right">
          <ResultCard
            result={result}
            stageIndex={stageIndex}
            running={running}
            progress={progress}
            progressText={progressText}
            error={error}
            onStage={setStageIndex}
          />
        </div>
      </main>
    </div>
  );
}
