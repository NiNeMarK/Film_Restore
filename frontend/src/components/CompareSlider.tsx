import { useCallback, useRef, useState } from "react";

type Props = {
  before: string;
  after: string;
};

/** สไลเดอร์เทียบก่อน/หลัง — ลากเส้นกลางได้ (เมาส์/ทัช) */
export default function CompareSlider({ before, after }: Props) {
  const [pos, setPos] = useState(50);
  const ref = useRef<HTMLDivElement>(null);

  const move = useCallback((clientX: number) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0) return;
    const next = ((clientX - rect.left) / rect.width) * 100;
    setPos(Math.min(100, Math.max(0, next)));
  }, []);

  return (
    <div
      className="compare"
      ref={ref}
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        move(event.clientX);
      }}
      onPointerMove={(event) => {
        if (event.buttons === 1) move(event.clientX);
      }}
    >
      <img className="compare-img" src={before} alt="ก่อนฟื้นฟู" draggable={false} />
      <img
        className="compare-img compare-after"
        src={after}
        alt="หลังฟื้นฟู"
        draggable={false}
        style={{ clipPath: `inset(0 0 0 ${pos}%)` }}
      />
      <div className="compare-handle" style={{ left: `${pos}%` }}>
        <span className="compare-grip" />
      </div>
      <span className="compare-tag compare-tag-before">ก่อน</span>
      <span className="compare-tag compare-tag-after">หลัง</span>
    </div>
  );
}
