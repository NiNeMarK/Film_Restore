import type { JobResult } from "../types";
import CompareSlider from "./CompareSlider";
import { ImageIcon } from "./icons";

type ResultThumb = { id: string; thumb: string; label: string; active: boolean };

type Props = {
  result: JobResult | null;
  stageIndex: number;
  running: boolean;
  progress: number;
  progressText: string;
  error: string | null;
  results: ResultThumb[];
  onStage: (index: number) => void;
  onPickResult: (id: string) => void;
  onApplySettings: (result: JobResult) => void;
};

function buildLog(result: JobResult): string {
  const last = result.stages[result.stages.length - 1];
  const lines = [
    `โหมด: ${result.preset_label}`,
    `ต้นฉบับ: ${result.original.width}×${result.original.height} px, ${result.original.bits}-bit`,
    `ผลลัพธ์: ${last ? `${last.width}×${last.height}` : "-"} px`,
    `ใช้เวลา: ${result.elapsed.toFixed(1)} วินาที`,
    `อุปกรณ์: ${result.meta.device === "cpu" ? "CPU" : `${result.meta.gpu} (${result.meta.device})`}`,
    "",
  ];
  for (const stage of result.stages) {
    lines.push(`[${stage.seconds.toFixed(1).padStart(5)}s] ${stage.label}: ${stage.note}`);
  }
  if (result.warnings.length) {
    lines.push("", "คำเตือน:", ...result.warnings.map((warning) => `- ${warning}`));
  }
  return lines.join("\n");
}

export default function ResultCard({
  result,
  stageIndex,
  running,
  progress,
  progressText,
  error,
  results,
  onStage,
  onPickResult,
  onApplySettings,
}: Props) {
  const active = result && stageIndex >= 0 ? result.stages[stageIndex] : null;

  return (
    <section className="card">
      <header className="card-head">
        <h2>
          <ImageIcon />
          ผลลัพธ์
        </h2>
        <span className="hint">ลากเส้นกลางภาพเพื่อเทียบก่อน/หลัง</span>
      </header>

      {error && <p className="error">{error}</p>}

      {result ? (
        <CompareSlider before={result.original_url} after={active ? active.url : result.result_url} />
      ) : (
        <div className="result-empty">
          {running ? (
            <>
              <div className="spinner" />
              <span>
                กำลังฟื้นฟู… {Math.round(progress * 100)}%
                <em>{progressText}</em>
              </span>
            </>
          ) : (
            <span>ผลลัพธ์จะแสดงที่นี่ — เลือกภาพแล้วกด «ฟื้นฟูภาพ»</span>
          )}
        </div>
      )}

      {result && (
        <div className="stages" role="list">
          {result.stages.map((stage, index) => (
            <button
              key={stage.key}
              type="button"
              role="listitem"
              className={`stage${index === stageIndex ? " is-on" : ""}`}
              title={`${stage.label} — ${stage.note}`}
              onClick={() => onStage(index)}
            >
              <img src={stage.url} alt={stage.label} loading="lazy" />
              <span>{stage.label}</span>
            </button>
          ))}
        </div>
      )}

      {results.length > 1 && (
        <div className="results-strip" role="list" aria-label="ผลลัพธ์ทุกภาพ">
          {results.map((item, index) => (
            <button
              key={item.id}
              type="button"
              role="listitem"
              className={`result-thumb${item.active ? " is-on" : ""}`}
              title={item.label}
              onClick={() => onPickResult(item.id)}
            >
              <img src={item.thumb} alt={item.label} loading="lazy" />
              <span>{index + 1}</span>
            </button>
          ))}
        </div>
      )}

      <pre className={`log${result ? "" : " is-empty"}`}>
        {result ? buildLog(result) : "ยังไม่มีผลลัพธ์ — เลือกภาพทางซ้ายแล้วกด «ฟื้นฟูภาพ»"}
      </pre>

      {result && (
        <div className="result-actions">
          <a
            href={`/download/${result.job}/result.png`}
            download={`film-restore_${result.job}.png`}
            className="download-link"
          >
            ดาวน์โหลดผลลัพธ์
          </a>
          <a href={`/download/${result.job}/settings.json`} download={`film-restore_${result.job}_settings.json`}>
            settings.json
          </a>
          <button type="button" className="link-button" onClick={() => onApplySettings(result)}>
            ใช้ค่านี้กับการตั้งค่า
          </button>
          <span className="hint">{active ? `กำลังดูขั้น: ${active.label}` : "กำลังดูผลลัพธ์สุดท้าย"}</span>
        </div>
      )}
    </section>
  );
}
