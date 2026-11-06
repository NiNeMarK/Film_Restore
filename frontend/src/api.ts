import type { Health, JobResult, PresetsResponse, Settings } from "./types";

const API = ""; // เสิร์ฟจาก origin เดียวกัน (FastAPI) — ตอน dev ใช้ proxy ของ Vite

export async function fetchHealth(): Promise<Health> {
  const res = await fetch(`${API}/api/health`);
  if (!res.ok) throw new Error(`โหลดข้อมูลเครื่องไม่สำเร็จ (${res.status})`);
  return res.json();
}

export async function fetchPresets(): Promise<PresetsResponse> {
  const res = await fetch(`${API}/api/presets`);
  if (!res.ok) throw new Error(`โหลดโหมดไม่สำเร็จ (${res.status})`);
  return res.json();
}

export function toOverrides(settings: Settings) {
  return {
    invert: settings.invert,
    color_fix: settings.color_fix,
    color_fix_strength: settings.color_fix_strength,
    scratch: settings.scratch,
    scratch_strength: settings.scratch_strength,
    denoise: settings.denoise,
    colorize: settings.colorize,
    colorize_strength: settings.colorize_strength,
    upscale: settings.upscale,
    face: settings.face,
    invert_gamma: settings.invert_gamma,
    final_wb: settings.final_wb,
    final_contrast: settings.final_contrast,
    final_saturation: settings.final_saturation,
    final_grain: settings.final_grain,
  };
}

export type RunOptions = {
  preset: string;
  settings: Settings;
  cropBorder: boolean;
};

/**
 * ส่งงานผ่าน WebSocket เพื่อรับความคืบหน้าระหว่างทาง
 * protocol: ส่ง text JSON (ตั้งค่า) ตามด้วย binary ภาพ แล้วรอ event progress/done/error
 */
export function runRestore(
  file: File,
  { preset, settings, cropBorder }: RunOptions,
  onProgress: (value: number, message: string) => void,
): Promise<JobResult> {
  return new Promise((resolve, reject) => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    let ws: WebSocket;
    try {
      ws = new WebSocket(`${proto}//${location.host}/ws/restore`);
    } catch (err) {
      reject(err);
      return;
    }

    let settled = false;
    const finish = (action: () => void) => {
      if (settled) return;
      settled = true;
      try {
        ws.close();
      } catch {
        /* ปิดแล้ว */
      }
      action();
    };

    ws.onopen = async () => {
      try {
        ws.send(
          JSON.stringify({
            preset,
            overrides: toOverrides(settings),
            crop_border: cropBorder,
            filename: file.name,
          }),
        );
        ws.send(await file.arrayBuffer());
      } catch (err) {
        finish(() => reject(err instanceof Error ? err : new Error(String(err))));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);
        if (msg.type === "progress") {
          onProgress(Number(msg.progress) || 0, String(msg.message || ""));
        } else if (msg.type === "done") {
          finish(() => resolve(msg as JobResult));
        } else if (msg.type === "error") {
          finish(() => reject(new Error(String(msg.detail || "ประมวลผลไม่สำเร็จ"))));
        }
      } catch (err) {
        finish(() => reject(err instanceof Error ? err : new Error(String(err))));
      }
    };

    ws.onerror = () => finish(() => reject(new Error("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้")));
    ws.onclose = () => finish(() => reject(new Error("การเชื่อมต่อปิดก่อนได้รับผลลัพธ์")));
  });
}
