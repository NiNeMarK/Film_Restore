import { useCallback, useEffect, useRef, useState } from "react";
import CompareSlider from "./CompareSlider";

type Mode = "compare" | "before" | "after";

type Props = {
  before: string;
  after: string;
  title?: string;
  onClose: () => void;
};

/** ดูผลลัพธ์เต็มหน้าต่าง — เทียบก่อน/หลัง, ดูภาพเดี่ยว, ซูม/เลื่อนได้ */
export default function Lightbox({ before, after, title, onClose }: Props) {
  const [mode, setMode] = useState<Mode>("compare");
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const stageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const clampZoom = (value: number) => Math.min(6, Math.max(1, Math.round(value * 100) / 100));

  const reset = useCallback(() => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  const setZoomAt = useCallback(
    (next: number) => {
      const value = clampZoom(next);
      setZoom(value);
      if (value === 1) setOffset({ x: 0, y: 0 });
    },
    [],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      else if (event.key === "1") setMode("compare");
      else if (event.key === "2") setMode("before");
      else if (event.key === "3") setMode("after");
      else if (event.key === "+" || event.key === "=") setZoomAt(zoom * 1.25);
      else if (event.key === "-") setZoomAt(zoom / 1.25);
      else if (event.key === "0") reset();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, reset, setZoomAt, zoom]);

  // ล้อเมาส์ = ซูม (โหมดดูภาพเดี่ยว)
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || mode === "compare") return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      setZoomAt(zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12));
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [mode, setZoomAt, zoom]);

  const image = mode === "before" ? before : after;

  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label={title ?? "ผลลัพธ์"}>
      <header className="lightbox-bar">
        <span className="lightbox-title">{title ?? "ผลลัพธ์"}</span>

        <div className="lightbox-group" role="group" aria-label="โหมดแสดงผล">
          <button type="button" className={mode === "compare" ? "is-on" : ""} onClick={() => setMode("compare")}>
            เทียบก่อน/หลัง
          </button>
          <button type="button" className={mode === "before" ? "is-on" : ""} onClick={() => setMode("before")}>
            ต้นฉบับ
          </button>
          <button type="button" className={mode === "after" ? "is-on" : ""} onClick={() => setMode("after")}>
            ผลลัพธ์
          </button>
        </div>

        <div className="lightbox-group">
          <button type="button" onClick={() => setZoomAt(zoom / 1.25)} aria-label="ย่อ">
            −
          </button>
          <span className="lightbox-zoom-value">{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => setZoomAt(zoom * 1.25)} aria-label="ขยาย">
            +
          </button>
          <button type="button" onClick={reset}>
            พอดีจอ
          </button>
        </div>

        <button type="button" className="lightbox-close" onClick={onClose} aria-label="ปิด">
          ✕
        </button>
      </header>

      <div
        className={`lightbox-stage${mode === "compare" ? " is-compare" : ""}`}
        ref={stageRef}
        onDoubleClick={reset}
        onPointerDown={(event) => {
          if (mode === "compare") return;
          dragRef.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          const drag = dragRef.current;
          if (!drag) return;
          setOffset({ x: drag.ox + (event.clientX - drag.x), y: drag.oy + (event.clientY - drag.y) });
        }}
        onPointerUp={() => {
          dragRef.current = null;
        }}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
      >
        {mode === "compare" ? (
          <CompareSlider className="compare compare--full" before={before} after={after} />
        ) : (
          <img
            src={image}
            alt={mode === "before" ? "ต้นฉบับ" : "ผลลัพธ์"}
            draggable={false}
            style={{
              transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
              cursor: zoom > 1 ? "grab" : "default",
            }}
          />
        )}
      </div>

      <p className="lightbox-hint">
        ลากเส้นกลางภาพเพื่อเทียบ · เลื่อนล้อเมาส์เพื่อซูม · ดับเบิลคลิกเพื่อรีเซ็ต · กด Esc เพื่อปิด
      </p>
    </div>
  );
}
