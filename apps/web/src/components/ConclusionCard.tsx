import type { EventDetail } from "../types";
import { formatDateTime, statusDetailChips } from "../utils";

type Props = {
  event: EventDetail;
  onOpenDiff: (from: number, to: number) => void;
  onExport: () => void;
};

export default function ConclusionCard({ event, onOpenDiff, onExport }: Props) {
  const chips = statusDetailChips(event.status_detail);
  const factCount = event.claims.filter(
    (claim) => claim.claim_role === "acquisition_fact" && claim.status === "active",
  ).length;
  const denialCount = event.claims.filter((claim) => claim.claim_type === "denial").length;
  const rumorCount = event.claims.filter((claim) => claim.claim_type === "rumor").length;
  const latest = event.revision.version;

  return (
    <section className={`conclusion-card ${event.is_replay ? "replay" : ""}`}>
      {event.is_replay && (
        <div className="replay-ribbon">
          回放中 · 只显示 {formatDateTime(event.as_of)} 之前已知的证据
        </div>
      )}
      <div className="conclusion-top">
        <div>
          <div className="eyebrow light">PINNED / 系统置顶</div>
          <h2>当前结论</h2>
        </div>
        <div className="conclusion-strength">
          <strong>{Math.round(event.evidence_strength)}</strong>
          <span>证据强度 / 100</span>
        </div>
      </div>

      <p className="conclusion-summary">{event.summary}</p>

      <div className="conclusion-chips">
        {chips.map((chip) => (
          <span className={`status-chip tone-${chip.tone}`} key={chip.label}>
            {chip.label}
          </span>
        ))}
      </div>

      <div className="conclusion-foot">
        <div className="conclusion-counts">
          <span>
            <b>{factCount}</b> 条交易事实
          </span>
          <span>
            <b>{denialCount}</b> 条官方否认
          </span>
          <span>
            <b>{rumorCount}</b> 条传闻
          </span>
          <span>
            <b>{event.sources_count}</b> 份官方披露
          </span>
        </div>
        <div className="conclusion-actions">
          {latest > 2 && (
            <button className="ghost-button" onClick={() => onOpenDiff(2, 3)}>
              看否认 diff
            </button>
          )}
          {latest > 1 && (
            <button className="ghost-button" onClick={() => onOpenDiff(latest - 1, latest)}>
              最新 diff
            </button>
          )}
          <button className="solid-button" onClick={onExport}>
            导出证据包
          </button>
        </div>
      </div>
    </section>
  );
}

