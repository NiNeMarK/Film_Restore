export type GpuInfo = {
  backend: string;
  device: string;
  name: string;
  total_vram_gb: number;
  free_vram_gb: number;
  fp16: boolean;
  tile_size: number;
  can_diffusion: boolean;
  torch_available: boolean;
  notes: string[];
};

export type ModelInfo = {
  key: string;
  label: string;
  license: string;
  note: string;
  approx_mb: number;
  downloaded: boolean;
  path: string;
};

export type Health = {
  status: string;
  gpu: GpuInfo;
  models: ModelInfo[];
};

export type Settings = {
  invert: "color" | "bw" | null;
  color_fix: boolean;
  color_fix_strength: number;
  scratch: boolean;
  scratch_strength: number;
  denoise: number;
  colorize: boolean;
  colorize_strength: number;
  upscale: number;
  face: number | null;
  invert_gamma: number;
  final_wb: number;
  final_contrast: number;
  final_saturation: number;
  final_grain: number;
};

export type PresetsResponse = {
  labels: Record<string, string>;
  notes: Record<string, string>;
  defaults: Record<string, Settings>;
};

export type Stage = {
  key: string;
  label: string;
  width: number;
  height: number;
  seconds: number;
  note: string;
  url: string;
};

export type JobResult = {
  type: "done";
  preset: string;
  preset_label: string;
  settings: Settings;
  meta: { device: string; gpu: string; fp16: boolean; tile_size: number };
  stages: Stage[];
  warnings: string[];
  elapsed: number;
  job: string;
  original: { width: number; height: number; bits: number };
  original_url: string;
  result_url: string;
};

export type ProgressEvent = { type: "progress"; progress: number; message: string };
