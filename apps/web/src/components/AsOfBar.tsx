import type { EventDetail } from "../types";
import { formatDateTime } from "../utils";

type Props = {
  variants: EventDetail["available_as_of"];
  value: string | null;
  onChange: (value: string | null) => void;
};

export default function AsOfBar({ variants, value, onChange }: Props) {
  const currentIndex = value
    ? Math.max(
        0,
        variants.findIndex((variant) => variant.knowledge_at === value),
      )
    : variants.length - 1;

  const selectIndex = (index: number) => {
    if (index >= variants.length - 1) onChange(null);
    else onChange(variants[index].knowledge_at);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <section className={`asof-bar ${value ? "is-replaying" : ""}`}>
      <div className="asof-head">
        <div>
          <div className="eyebrow">AS-OF REPLAY / 按当时已知回放</div>
          <strong>
            {value ? `正在回放 ${formatDateTime(value)}` : "当前视图"}
          </strong>
        </div>
        {value && (
          <button className="quiet-button" onClick={() => onChange(null)}>
            退出回放
          </button>
        )}
      </div>

      <div className="asof-presets">
        {variants.map((variant, index) => {
          const active = index === currentIndex;
          return (
            <button
              key={variant.version}
              className={`asof-preset ${active ? "active" : ""}`}
              onClick={() => selectIndex(index)}
            >
              <span>v{variant.version}</span>
              <b>{variant.label}</b>
              <small>{formatDateTime(variant.knowledge_at)}</small>
            </button>
          );
        })}
      </div>

      <div className="asof-slider">
        <input
          type="range"
          min={0}
          max={variants.length - 1}
          step={1}
          value={currentIndex}
          onChange={(event) => selectIndex(Number(event.target.value))}
          aria-label="选择回放时间"
        />
        <div className="asof-ticks">
          {variants.map((variant) => (
            <span key={variant.version}>{variant.label}</span>
          ))}
        </div>
      </div>
      <p className="asof-note">
        回放只使用该时刻之前已知的版本；未来证据自动隐藏。时间点若为推断，会标注“推断”。
      </p>
    </section>
  );
}

