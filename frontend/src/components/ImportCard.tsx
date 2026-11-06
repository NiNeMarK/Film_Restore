import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { CloseIcon, UploadIcon } from "./icons";

type Props = {
  file: File | null;
  previewUrl: string | null;
  running: boolean;
  progress: number;
  progressText: string;
  onFile: (file: File | null) => void;
  onRun: () => void;
};

const ACCEPT = ".jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp,.nef,.cr2,.arw,.dng";

function prettySize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function ImportCard({
  file,
  previewUrl,
  running,
  progress,
  progressText,
  onFile,
  onRun,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const takeFile = (candidate: File | undefined) => {
    if (candidate) onFile(candidate);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    takeFile(event.dataTransfer.files[0]);
  };

  return (
    <section className="card card--warm">
      <header className="card-head">
        <h2>
          <UploadIcon />
          ภาพต้นฉบับ
        </h2>
        <span className="hint">JPG · TIFF · RAW</span>
      </header>

      <div className="import">
        <div
          className={`dropzone${dragging ? " is-drag" : ""}${file ? " has-file" : ""}`}
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
          {file ? (
            <>
              <span className="file-chip">
                <span className="file-name" title={file.name}>
                  {file.name}
                </span>
                <span className="file-size">{prettySize(file.size)}</span>
                <button
                  type="button"
                  className="file-clear"
                  aria-label="เอาไฟล์ออก"
                  onClick={(event) => {
                    event.stopPropagation();
                    onFile(null);
                  }}
                >
                  <CloseIcon />
                </button>
              </span>
              <span className="dropzone-sub">คลิกเพื่อเปลี่ยนภาพ</span>
            </>
          ) : (
            <span className="dropzone-empty">
              <UploadIcon />
              ลากไฟล์มาวาง หรือคลิกเพื่อเลือก
            </span>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            hidden
            onChange={(event) => {
              takeFile(event.target.files?.[0]);
              // ล้างค่าไว้ เพื่อให้เลือกไฟล์เดิมซ้ำได้อีก
              event.target.value = "";
            }}
          />
        </div>

        {previewUrl && <img className="import-thumb" src={previewUrl} alt="ตัวอย่างภาพต้นฉบับ" />}
      </div>

      <button className="run" type="button" onClick={onRun} disabled={!file || running}>
        {running ? "กำลังฟื้นฟู…" : "ฟื้นฟูภาพ"}
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
