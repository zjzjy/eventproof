import type { Claim, EventDetail } from "../types";
import {
  claimTypeClass,
  claimTypeLabel,
  formatDate,
  formatDateTime,
  sourceTierLabel,
  statusLabel,
  strengthBandLabel,
} from "../utils";

type Props = {
  claim: Claim | null;
  event: EventDetail;
  onClose: () => void;
};

const FACTORS: Array<[string, string]> = [
  ["authority", "权威性"],
  ["directness", "直接性"],
  ["independence", "独立性"],
  ["specificity", "具体性"],
  ["corroboration", "佐证度"],
  ["extraction", "抽取置信"],
];

export default function EvidenceDrawer({ claim, event, onClose }: Props) {
  const doc = claim ? event.documents.find((item) => item.id === claim.document_id) : null;

  return (
    <aside className={`evidence-drawer ${claim ? "has-selection" : ""}`}>
      <div className="drawer-head">
        <div>
          <div className="eyebrow">EVIDENCE / 证据</div>
          <h2>{claim ? "这条结论凭什么" : "选择一条主张"}</h2>
        </div>
        {claim && (
          <button className="icon-button" onClick={onClose} aria-label="关闭证据抽屉">
            ×
          </button>
        )}
      </div>

      {!claim && (
        <div className="drawer-empty">
          <div className="empty-mark">↗</div>
          <p>点击事件串里的任意一条主张，查看原文引用、来源层级、抓取时间和权重拆解。</p>
          <div className="drawer-stat-grid">
            <div>
              <strong>{event.claims.length}</strong>
              <span>当前可见主张</span>
            </div>
            <div>
              <strong>{event.sources_count}</strong>
              <span>官方披露</span>
            </div>
            <div>
              <strong>{event.independent_sources_count}</strong>
              <span>独立披露主体</span>
            </div>
            <div>
              <strong>{event.denied_claims_count}</strong>
              <span>已否认主张</span>
            </div>
          </div>
          <div className="drawer-note">
            <strong>阅读规则</strong>
            <p>本事件串只收录来源与证据，不开放用户评论；转载不增加独立性，传闻不因传播次数变强。</p>
          </div>
        </div>
      )}

      {claim && doc && (
        <div className="drawer-body">
          <div className="drawer-claim-head">
            <span className={`type-chip type-${claimTypeClass[claim.claim_type]}`}>
              {claimTypeLabel[claim.claim_type]}
            </span>
            <span className={`state-chip state-${claim.status}`}>{statusLabel[claim.status]}</span>
            <span className="drawer-strength">
              {claim.strength}
              <small>/100</small>
            </span>
          </div>
          <p className="drawer-claim-text">{claim.text}</p>

          <div className="quote-card">
            <div className="quote-label">原文引用</div>
            <blockquote>“{claim.quote}”</blockquote>
            <div className="quote-source">
              <span>{doc.title}</span>
              <a href={doc.url} target="_blank" rel="noreferrer">
                打开原文 ↗
              </a>
            </div>
          </div>

          <div className="meta-grid">
            <div>
              <span>来源</span>
              <strong>{doc.source}</strong>
            </div>
            <div>
              <span>来源层级</span>
              <strong>{sourceTierLabel[doc.source_tier] ?? doc.source_tier}</strong>
            </div>
            <div>
              <span>披露时间</span>
              <strong>
                {formatDate(doc.published_at)}
                <small>（日期级）</small>
              </strong>
            </div>
            <div>
              <span>进入系统</span>
              <strong>
                {formatDateTime(claim.introduced_at)}
                <small>{claim.is_inferred ? "（推断）" : ""}</small>
              </strong>
            </div>
          </div>

          <div className="strength-panel">
            <div className="panel-title">
              <span>证据强度拆解</span>
              <span className={`band band-${claim.strength_band}`}>
                {strengthBandLabel(claim.strength_band)}
              </span>
            </div>
            {FACTORS.map(([key, label]) => {
              const value = Math.round(Number(claim.strength_json?.[key] ?? 0) * 100);
              return (
                <div className="factor-row" key={key}>
                  <span>{label}</span>
                  <div className="factor-track">
                    <i style={{ width: `${value}%` }} />
                  </div>
                  <b>{value}</b>
                </div>
              );
            })}
            <p className="factor-explain">{claim.strength_explanation}</p>
          </div>

          <div className="drawer-note">
            <strong>传播链</strong>
            <p>
              {event.sources_count} 篇官方披露 · {event.independent_sources_count} 个披露主体 · 0
              篇独立转载。转载不增加独立性。
            </p>
          </div>

          {claim.claim_type === "rumor" && (
            <div className="drawer-warning">
              <strong>传闻上限 35 分</strong>
              <p>
                这条说法来自网络媒体转述，未获得原始报道；即使被多家转载，也只算一个来源。
              </p>
            </div>
          )}

          {claim.status === "denied" && (
            <div className="drawer-warning red">
              <strong>已被官方否认</strong>
              <p>否认作为独立 claim 记录；原传闻保留在版本链里，方便回放“当时怎么判断”。</p>
            </div>
          )}

          <div className="drawer-boundary">
            <strong>边界</strong>
            <p>证据强度是可解释的启发式评分，不是“事实为真的概率”，也不构成投资建议。</p>
          </div>
        </div>
      )}
    </aside>
  );
}

