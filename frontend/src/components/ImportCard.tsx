import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { CloseIcon, UploadIcon } from "./icons";

export type ItemView = {
  id: string;
  name: string;
  size: number;
  status: "queued" | "running" | "done" | "error";
  thumb: string;
  error?: string;
};

type Props = {
  items: ItemView[];
  activeId: string | null;
  previewUrl: string | null;
  running: boolean;
  progress: number;
  progressText: string;
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
  onSelect: (id: string) => void;
  onRun: () => void;
};

const ACCEPT = ".jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp,.nef,.cr2,.arw,.dng";

const STATUS_LABEL: Record<ItemView["status"], string> = {
  queued: "รอ",
  running: "กำลังทำ",
  done: "เสร็จ",
  error: "ผิดพลาด",
};

function prettySize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function ImportCard({
  items,
  activeId,
  previewUrl,
  running,
  progress,
  progressText,
  onAdd,
  onRemove,
  onSelect,
  onRun,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pending = items.filter((item) => item.status !== "done").length;
  const label = running
    ? "กำลังฟื้นฟู…"
    : items.length === 0
      ? "ฟื้นฟูภาพ"
      : pending > 0
        ? `ฟื้นฟู ${pending} ภาพ`
        : "ฟื้นฟูซ้ำทั้งหมด";

  const take = (list: FileList | null) => {
    if (!list) return;
    const files = Array.from(list);
    if (files.length) onAdd(files);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    take(event.dataTransfer.files);
  };

  return (
    <section className="card card--warm">
      <header className="card-head">
        <h2>
          <UploadIcon />
          ภาพต้นฉบับ
        </h2>
        <span className="hint">
          JPG · TIFF · RAW {items.length > 0 && `· ${items.length} ภาพ`}
        </span>
      </header>

      <div className="import">
        <div
          className={`dropzone${dragging ? " is-drag" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <span className="dropzone-empty">
            <UploadIcon />
            {items.length ? "ลากไฟล์เพิ่ม หรือคลิกเพื่อเลือก" : "ลากไฟล์มาวาง หรือคลิกเพื่อเลือก"}
          </span>
          <span className="dropzone-sub">เลือกได้หลายภาพพร้อมกัน</span>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            multiple
            hidden
            onChange={(event) => {
              take(event.target.files);
              event.target.value = "";
            }}
          />
        </div>

        {previewUrl && (
          <div className="import-preview">
            <img src={previewUrl} alt="พรีวิวภาพต้นฉบับ" />
            <span className="preview-badge">พรีวิว</span>
          </div>
        )}
      </div>

      {items.length > 0 && (
        <ul className="file-list">
          {items.map((item) => (
            <li key={item.id} className={item.id === activeId ? "is-active" : ""}>
              <button type="button" className="file-row" onClick={() => onSelect(item.id)} title={item.name}>
                <img src={item.thumb} alt="" />
                <span className="file-name">{item.name}</span>
                <span className="file-size">{prettySize(item.size)}</span>
                <span className={`file-status is-${item.status}`}>
                  {item.error ? item.error : STATUS_LABEL[item.status]}
                </span>
              </button>
              <button
                type="button"
                className="file-clear"
                aria-label="เอาไฟล์ออก"
                onClick={() => onRemove(item.id)}
              >
                <CloseIcon />
              </button>
            </li>
          ))}
        </ul>
      )}

      <button className="run" type="button" onClick={onRun} disabled={items.length === 0 || running}>
        {label}
      </button>

      {running && (
        <div className="progress" role="progressbar" aria-valuenow={Math.round(progress * 100)}>
          <div className="progress-bar" style={{ width: `${Math.round(progress * 100)}%` }} />
          <span className="progress-text">{progressText}</span>
        </div>
      )}
    </section>
  );
}
